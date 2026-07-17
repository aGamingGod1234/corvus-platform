import { afterEach, describe, expect, it, vi } from "vitest";

import { createCorvusApi } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status
  });
}

describe("legacy Corvus transport authority", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses credentialed legacy session truth and its CSRF token for mutations", async () => {
    const requests: Request[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      requests.push(request);
      if (request.url.endsWith("/api/auth/session")) {
        return jsonResponse({
          csrf_token: "transport-csrf",
          username: "operator",
          user_id: "operator-1",
          tenant_id: "local",
          expires_at: "2026-07-18T00:00:00Z"
        });
      }
      return jsonResponse({
        id: "project-1",
        name: "Launch control",
        tenant_id: "local",
        created_at: "2026-07-17T00:00:00Z"
      });
    }));
    const api = createCorvusApi("http://127.0.0.1:8080");

    await api.session();
    await api.createProject("Launch control");

    expect(requests[0].url).toBe("http://127.0.0.1:8080/api/auth/session");
    expect(requests[0].credentials).toBe("include");
    expect(requests[1].headers.get("X-CSRF-Token")).toBe("transport-csrf");
  });

  it("exchanges a pairing value, reloads the real session, and consumes its CSRF token", async () => {
    const requests: Request[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const request = input as Request;
      requests.push(request);
      if (request.url.endsWith("/api/auth/pair")) return new Response(null, { status: 204 });
      if (request.url.endsWith("/api/auth/session")) {
        return jsonResponse({
          csrf_token: "paired-transport-csrf",
          username: "operator",
          user_id: "operator-1",
          tenant_id: "local",
          expires_at: "2026-07-18T00:00:00Z"
        });
      }
      return jsonResponse({
        id: "project-1",
        name: "Launch control",
        tenant_id: "local",
        created_at: "2026-07-17T00:00:00Z"
      });
    }));
    const api = createCorvusApi("http://127.0.0.1:8080");

    await api.pair("one-time-pairing-value");
    await api.createProject("Launch control");

    expect(requests.map((request) => new URL(request.url).pathname)).toEqual([
      "/api/auth/pair",
      "/api/auth/session",
      "/api/projects"
    ]);
    expect(requests.every((request) => request.credentials === "include")).toBe(true);
    expect(requests[2].headers.get("X-CSRF-Token")).toBe("paired-transport-csrf");
  });
});
