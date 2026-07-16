# Hosted runtime security contract

## Alpha network decision

The `v0.2.0-alpha.1` Vercel surface is a static runtime chooser and Cloud Preview. No external
streaming or API origin is required for the alpha. The local workspace uses same-origin `/api/*`
requests and a same-origin `EventSource` endpoint only after the browser has navigated away from
Vercel to the local Corvus origin. Therefore the deployed Content Security Policy deliberately
keeps `connect-src 'self'`.

The full-product `/api/v2/**` identity surface remains same-origin in the browser and is forwarded
by a Vercel function to one configured Railway service. Production and preview accept only a
credential-free HTTPS hostname ending in `.up.railway.app`; arbitrary custom domains, IP literals,
private/link-local addresses, userinfo, paths, queries, and fragments are rejected. Custom Railway
domains remain unsupported until an explicit deployment allowlist is designed and reviewed.

Loopback proxy origins are accepted only when the function receives an explicit `development` or
`test` environment. They are rejected in production, preview, and unspecified environments.
Adding E2B or any other hosted API, SSE, or WebSocket origin still requires an explicit CSP change,
a security review, and regression coverage. Wildcard network origins are not permitted.

## Loopback handoff trust status

The hosted page uses a user-initiated link to `http://127.0.0.1:8080/`; it does not fetch the local
service or send it a session, pairing value, or HMAC secret. This is an unverified trust boundary:
the alpha cannot prove which local process owns port 8080. The UI discloses that limitation and
requires the user to start Corvus before following the link.

A real local-app challenge requires a trusted bootstrap channel, such as a native custom protocol
or a desktop-issued capability. That work belongs to the native runtime-selector milestone. It must
not be simulated with a nonce that an arbitrary loopback process could echo, and it must not expose
a local capability to Vercel.
