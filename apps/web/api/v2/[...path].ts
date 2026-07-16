const API_PREFIX = "/api/v2";
const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);
const ALLOWED_METHODS = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"]);
const FORWARDED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "cookie",
  "idempotency-key",
  "origin",
  "x-csrf-token",
] as const;
const FORWARDED_RESPONSE_HEADERS = [
  "cache-control",
  "content-language",
  "content-type",
  "expires",
  "pragma",
  "vary",
] as const;
const BODY_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

declare const process: { env: Record<string, string | undefined> };

function errorResponse(status: number, code: string): Response {
  return Response.json({ detail: { code } }, { status });
}

function validatedOrigin(configuredOrigin: string | undefined): URL | null {
  if (configuredOrigin === undefined || configuredOrigin.trim() === "") return null;
  let parsed: URL;
  try {
    parsed = new URL(configuredOrigin);
  } catch {
    return null;
  }
  const secure = parsed.protocol === "https:";
  const loopback = parsed.protocol === "http:" && LOOPBACK_HOSTS.has(parsed.hostname);
  if (
    (!secure && !loopback) ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    parsed.pathname !== "/" ||
    parsed.search !== "" ||
    parsed.hash !== ""
  ) {
    return null;
  }
  return parsed;
}

function safeApiPath(requestUrl: URL): string | null {
  const path = requestUrl.pathname;
  if (path !== API_PREFIX && !path.startsWith(`${API_PREFIX}/`)) return null;
  if (/%(?:2e|2f|5c)/i.test(path) || path.includes("\\")) return null;
  const captured = path.slice(API_PREFIX.length);
  if (captured.includes("//")) return null;
  let decoded: string;
  try {
    decoded = decodeURIComponent(captured);
  } catch {
    return null;
  }
  if (
    decoded.includes("\\") ||
    decoded.includes("//") ||
    decoded.split("/").some((segment) => segment === "." || segment === "..")
  ) {
    return null;
  }
  return `${API_PREFIX}${captured}`;
}

function requestHeaders(request: Request): Headers {
  const forwarded = new Headers();
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) forwarded.set(name, value);
  }
  return forwarded;
}

function responseHeaders(upstream: Response): Headers {
  const forwarded = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) forwarded.set(name, value);
  }
  const location = upstream.headers.get("location");
  if (
    location !== null &&
    location.startsWith("/") &&
    !location.startsWith("//") &&
    !location.includes("\\") &&
    !/[\u0000-\u001f\u007f]/.test(location)
  ) {
    forwarded.set("location", location);
  }
  const cookieHeaders = upstream.headers as Headers & { getSetCookie?: () => string[] };
  const cookies = cookieHeaders.getSetCookie?.() ?? [];
  if (cookies.length > 0) {
    for (const cookie of cookies) forwarded.append("set-cookie", cookie);
  } else {
    const cookie = upstream.headers.get("set-cookie");
    if (cookie !== null) forwarded.append("set-cookie", cookie);
  }
  return forwarded;
}

export async function proxyV2Request(
  request: Request,
  configuredOrigin: string | undefined,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  const origin = validatedOrigin(configuredOrigin);
  if (origin === null) return errorResponse(503, "platform_proxy_unavailable");
  if (!ALLOWED_METHODS.has(request.method)) {
    return errorResponse(405, "platform_proxy_method_forbidden");
  }
  const requestUrl = new URL(request.url);
  const apiPath = safeApiPath(requestUrl);
  if (apiPath === null) return errorResponse(400, "platform_proxy_path_invalid");
  const target = `${origin.origin}${apiPath}${requestUrl.search}`;
  const body = BODY_METHODS.has(request.method) ? await request.arrayBuffer() : undefined;
  let upstream: Response;
  try {
    upstream = await fetchImpl(target, {
      method: request.method,
      headers: requestHeaders(request),
      body: body?.byteLength === 0 ? undefined : body,
      redirect: "manual",
    });
  } catch {
    return errorResponse(503, "platform_proxy_unavailable");
  }
  const bodyForbidden =
    request.method === "HEAD" || [204, 205, 304].includes(upstream.status);
  return new Response(bodyForbidden ? null : upstream.body, {
    status: upstream.status,
    headers: responseHeaders(upstream),
  });
}

export default {
  fetch(request: Request): Promise<Response> {
    return proxyV2Request(request, process.env.CORVUS_RAILWAY_ORIGIN);
  },
};
