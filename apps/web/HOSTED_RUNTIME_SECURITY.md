# Hosted runtime security contract

## Alpha network decision

The `v0.2.0-alpha.1` Vercel surface is a static runtime chooser and Cloud Preview. No external
streaming or API origin is required for the alpha. The local workspace uses same-origin `/api/*`
requests and a same-origin `EventSource` endpoint only after the browser has navigated away from
Vercel to the local Corvus origin. Therefore the deployed Content Security Policy deliberately
keeps `connect-src 'self'`.

Adding Railway, E2B, Google OAuth, or any other hosted API, SSE, or WebSocket origin requires an
explicit CSP change, a security review, and regression coverage. Wildcard network origins are not
permitted.

## Loopback handoff trust status

The hosted page uses a user-initiated link to `http://127.0.0.1:8080/`; it does not fetch the local
service or send it a session, pairing value, or HMAC secret. This is an unverified trust boundary:
the alpha cannot prove which local process owns port 8080. The UI discloses that limitation and
requires the user to start Corvus before following the link.

A real local-app challenge requires a trusted bootstrap channel, such as a native custom protocol
or a desktop-issued capability. That work belongs to the native runtime-selector milestone. It must
not be simulated with a nonce that an arbitrary loopback process could echo, and it must not expose
a local capability to Vercel.
