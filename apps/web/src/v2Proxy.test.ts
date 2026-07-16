import { describe, expect, it, vi } from "vitest";

import { proxyV2Request } from "../api/v2/[...path]";

const ORIGIN = "https://corvus-control.up.railway.app";

describe("same-origin v2 proxy", () => {
  it("returns a redacted 503 when the Railway origin is absent or invalid", async () => {
    const canary = "railway-origin-secret-canary";
    const fetchImpl = vi.fn<typeof fetch>();

    for (const configuredOrigin of [
      undefined,
      `https://user:${canary}@evil.example`,
      `https://railway.example/${canary}`,
      `https://railway.example?token=${canary}`,
    ]) {
      const response = await proxyV2Request(
        new Request("https://corvus.example/api/v2/session"),
        configuredOrigin,
        fetchImpl,
      );
      expect(response.status).toBe(503);
      expect(await response.text()).not.toContain(canary);
    }
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("forwards only the captured v2 path and explicit safe request headers", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const request = new Request(
      "https://corvus.example/api/v2/workspaces/example?include=members",
      {
        method: "PATCH",
        headers: {
          accept: "application/json",
          authorization: "Bearer must-not-forward",
          cookie: "__Host-corvus_v2_session=opaque",
          host: "evil.example",
          "idempotency-key": "request-1",
          origin: "https://corvus.example",
          "x-csrf-token": "csrf-value",
          "x-forwarded-host": "evil.example",
          "content-type": "application/json",
        },
        body: JSON.stringify({ name: "Safe" }),
      },
    );

    const response = await proxyV2Request(request, ORIGIN, fetchImpl);

    expect(response.status).toBe(200);
    expect(fetchImpl).toHaveBeenCalledOnce();
    const [target, init] = fetchImpl.mock.calls[0];
    expect(target).toBe(
      "https://corvus-control.up.railway.app/api/v2/workspaces/example?include=members",
    );
    expect(init?.method).toBe("PATCH");
    const headers = new Headers(init?.headers);
    expect(headers.get("cookie")).toBe("__Host-corvus_v2_session=opaque");
    expect(headers.get("origin")).toBe("https://corvus.example");
    expect(headers.get("x-csrf-token")).toBe("csrf-value");
    expect(headers.get("idempotency-key")).toBe("request-1");
    expect(headers.has("authorization")).toBe(false);
    expect(headers.has("host")).toBe(false);
    expect(headers.has("x-forwarded-host")).toBe(false);
    expect(init?.redirect).toBe("manual");
  });

  it.each([
    "/api/v2/../admin",
    "/api/v2/%2e%2e/admin",
    "/api/v2/%2f%2fevil.example/admin",
    "/api/v2/%5c%5cevil.example/admin",
    "/api/v2//evil.example/admin",
  ])("rejects traversal and encoded authority path %s", async (path) => {
    const fetchImpl = vi.fn<typeof fetch>();

    const response = await proxyV2Request(
      new Request(`https://corvus.example${path}`),
      ORIGIN,
      fetchImpl,
    );

    expect(response.status).toBe(400);
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(await response.text()).not.toContain(path);
  });

  it("preserves manual OAuth redirects, cookies, and safe response content headers", async () => {
    const upstreamHeaders = new Headers({
      "cache-control": "no-store",
      "content-type": "application/json",
      location: "/onboarding",
      "set-cookie": "__Host-corvus_v2_session=opaque; Secure; HttpOnly; Path=/",
      "x-upstream-secret": "must-not-forward",
    });
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, { status: 303, headers: upstreamHeaders }),
    );

    const response = await proxyV2Request(
      new Request("https://corvus.example/api/v2/auth/google/callback?code=opaque"),
      ORIGIN,
      fetchImpl,
    );

    expect(response.status).toBe(303);
    expect(response.headers.get("location")).toBe("/onboarding");
    expect(response.headers.get("set-cookie")).toContain("__Host-corvus_v2_session=opaque");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.has("x-upstream-secret")).toBe(false);
  });

  it("drops an external upstream redirect location", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(null, {
        status: 303,
        headers: { location: "https://evil.example/capture" },
      }),
    );

    const response = await proxyV2Request(
      new Request("https://corvus.example/api/v2/auth/google/callback"),
      ORIGIN,
      fetchImpl,
    );

    expect(response.status).toBe(303);
    expect(response.headers.has("location")).toBe(false);
  });
});
