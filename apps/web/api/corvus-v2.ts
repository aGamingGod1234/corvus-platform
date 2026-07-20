import { proxyV2Request } from "./v2/[...path].js";

declare const process: { env: Record<string, string | undefined> };

const REWRITE_PARAMETER = "corvusPath";

async function rewrittenRequest(request: Request): Promise<Request | null> {
  const source = new URL(request.url);
  const capturedPath = source.searchParams.get(REWRITE_PARAMETER);
  if (capturedPath === null || capturedPath === "" || capturedPath.startsWith("/")) return null;
  source.searchParams.delete(REWRITE_PARAMETER);
  source.pathname = `/api/v2/${capturedPath}`;
  const body = request.method === "GET" || request.method === "HEAD"
    ? undefined
    : await request.arrayBuffer();
  return new Request(source, {
    method: request.method,
    headers: request.headers,
    body: body?.byteLength === 0 ? undefined : body,
    redirect: request.redirect,
  });
}

export async function proxyRewrittenV2Request(
  request: Request,
  configuredOrigin: string | undefined,
  fetchImpl: typeof fetch = fetch,
  deploymentEnvironment: string | undefined = process.env.VERCEL_ENV,
): Promise<Response> {
  const rewritten = await rewrittenRequest(request);
  if (rewritten === null) {
    return Promise.resolve(Response.json(
      { detail: { code: "platform_proxy_path_invalid" } },
      { status: 400 },
    ));
  }
  return proxyV2Request(rewritten, configuredOrigin, fetchImpl, deploymentEnvironment);
}

export default {
  fetch(request: Request): Promise<Response> {
    return proxyRewrittenV2Request(
      request,
      process.env.CORVUS_RAILWAY_ORIGIN,
      fetch,
      process.env.VERCEL_ENV,
    );
  },
};
