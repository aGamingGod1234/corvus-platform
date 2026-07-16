# Corvus Frontend Project Context

- Generated: 2026-07-16
- Project root: `C:\Users\lucas\Documents\corvus\corvus-platform-pr4`
- Product goal: Complete the Corvus identity-backed agent platform.
- Audience: Everyday and developer individuals and teams.
- Primary conversion: Sign in and start a governed agent thread.
- Product type: authenticated web and Tauri desktop application.
- Approved design authority: `docs/superpowers/specs/2026-07-16-corvus-full-product-platform-design.md`.

## Product truth

Corvus is one governed agent product composed along two presentation axes: Everyday or Developer experience, and Individual or Team workspace. These choices alter language, density, and information architecture but never create authority. Google identity, workspace membership, policies, approvals, budgets, credentials, audit state, and runtime placement remain server-authoritative.

The seven designed surfaces are identity and onboarding, conversation, live run flightpath, scheduling, settings and integrations, team collaboration, and runtime continuity. The persistent conversion path is: sign in, choose a workspace, create a thread, and send a governed request.

## Existing implementation baseline

- React 19, TypeScript, Vite, and Vitest live in `apps/web`.
- Tauri v2 Rust commands live in `apps/desktop/src-tauri/src`.
- The current visual identity uses warm paper, ink, signal blue, copper, accessible teal, Fraunces, Inter Tight, IBM Plex Mono, graph lines, and a flightpath motif.
- The current app already has responsive navigation, onboarding, runtime truth states, keyboard focus treatment, and reduced-motion handling.

## Authority and delivery constraints

- Preserve existing domain contracts and truthful capability gates.
- Hosted web must never silently probe loopback.
- Profile labels are read-only identity context outside Settings.
- Team presentation never grants membership or capabilities.
- Cloud remains Preview until identity, placement, lifecycle, and cleanup gates pass.
- No dependency change is authorized by this packet.
- Product implementation is outside Task 1.1; this packet establishes selectors, interactions, responsive targets, provenance hooks, and the allowed change boundary.

## Approved responsive targets

- Desktop: `1440x1000`, three panes where useful: 240px navigation, fluid conversation, up to 360px inspector.
- Tablet: `1024x900`, navigation plus primary surface; inspector becomes a drawer.
- Mobile: `390x844`, thread-first surface, four bottom actions plus More, and full-screen sheets/inspector.
