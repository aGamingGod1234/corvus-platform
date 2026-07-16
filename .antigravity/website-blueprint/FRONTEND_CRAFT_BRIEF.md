# Corvus Frontend Craft Brief

This packet explicitly applies `website-design-blueprint` for provenance and approval, `impeccable` for finish and hierarchy, `design-motion-principles` for purposeful state motion, and the `frontend-design` skill for a subject-specific visual point of view.

## Viewer intent

The viewer wants to begin useful agent work quickly while understanding who owns the workspace, where the run executes, what authority it has, and when human approval is required. Everyday users should see outcomes before machinery. Developer users should reach precise evidence without changing products.

## Scene sentence

Corvus is a quiet field desk for governed agents: paper, graph lines, ink, a cobalt route, and copper approval marks organize one live flight from request to result.

## Aesthetic decision and signature

The single memorable move is the **live flightpath spine**. It begins at the composer, travels through Plan, Work, Approval, and Result, and can extend into the inspector to connect an event to its artifact or decision. This is operational structure, not decoration. All other surfaces stay restrained.

This direction preserves the approved warm-paper identity but avoids the generic cream-and-serif landing-page default: the paper is cool mineral rather than nostalgic, Fraunces appears only at decisive orientation moments, and the dominant experience is a precise sans conversation workspace.

## Color strategy

- Flight Paper `#F3F5F2`: primary canvas.
- Raised White `#FFFFFF`: composer, menus, and focused work surfaces.
- Raven Ink `#182330`: primary text and structural marks.
- Signal Cobalt `#2F6FED`: selected state, route progress, and primary action.
- Approval Copper `#C96C1A`: human decision points only.
- Team Teal `#167C78`: team scope accent, always paired with text/labels.
- Danger Red `#A63E37`: destructive and terminal states only.
- Rule Grey `#D8DEDB`: graph lines and separators.

No gradient is used as empty atmosphere. Color never grants authority or carries status without text, shape, and accessible semantics.

## Typography lane

- Display and orientation: `Fraunces Variable`, weight 520-620, used for onboarding decisions, empty-thread welcome, and major recovery headings only.
- Product body and controls: `Inter Tight Variable`, weight 450-700, optimized for readable conversation and compact action labels.
- Evidence and utility: `IBM Plex Mono`, used for run IDs, times, budgets, providers, reason codes, and flightpath labels.

The composer, messages, schedules, and settings use sans typography. Developer density comes from spacing and evidence disclosure, not tiny type.

## Layout system

- Desktop: 240px navigation, fluid conversation, optional inspector up to 360px; the composer stays within the conversation column.
- Tablet: navigation and primary surface; inspector and secondary filters become drawers.
- Mobile: thread-first, compact identity bar, persistent composer, four bottom actions plus More, and full-screen semantic sheets.
- Content uses rules, split planes, timelines, and lists before containers. Maximum generic cards: 3.

## Media hierarchy

This is a product application, so the primary media is live state: conversation text, the flightpath spine, artifact previews, schedule calendar marks, presence cursors, and runtime topology. Decorative stock imagery is prohibited. Avatars are optional identity aids, never the primary proof.

## Motion intent

One orchestrated sequence explains each run: the new user message settles, the cobalt path advances to Plan and Work, copper pauses at Approval, and the route resolves into Result. Streaming uses restrained opacity and position changes of 4px or less. Hover motion is limited to stateful controls. Drawers and inspector transitions preserve focus.

`prefers-reduced-motion: reduce` removes travel and transforms; state changes remain immediate and understandable. Motion evidence must include active animations plus a reduced-motion verification log, not screenshots alone.

## Source-derived choices

- Corvus sources define authority language, profile compositions, runtime truth, and the flightpath.
- ChatGPT informs a stable New thread entry, persistent history, and composer-led conversion.
- T3Code informs keeping provider/runtime context close to agent work without copying its chrome.
- shadcn Button informs semantic action states; Lucide Send informs the send glyph and accessible labeling.

Every major surface exposes `data-source-refs`. Adapted shadcn/Lucide controls additionally expose `data-component-source`.

## Interaction and accessibility floor

- Every control has an accessible name, visible focus, keyboard activation, and documented state change.
- Minimum target size is 44x44 CSS pixels on touch layouts.
- Status uses live regions without stealing focus.
- Closing sheets and inspectors restores focus to the trigger.
- Disabled controls state why they are unavailable.
- Error text names the problem, gives the next action, and preserves the last known-good state.

## Anti-patterns

- Generic dashboard card grids, KPI tiles, gradient blobs, glass panels, decorative command-line text, and fake terminal chrome.
- Profile switching in the top-left identity block.
- Technical density in Everyday profiles or hidden evidence in Developer profiles.
- Fake cloud readiness, fake sign-in, fake billing, optimistic authority, or silent loopback probing.
- Source notes, provenance language, internal process copy, TODOs, or implementation explanations in visible UI.
- Repeated treatment across adjacent surfaces.
- Motion that does not communicate run, approval, navigation, or recovery state.

## Self-critique before build

The warm-paper/Fraunces combination risks reading like a fashionable editorial template. The correction is to reserve Fraunces for orientation, keep the core work surface sans and operational, and make the flightpath a real state machine. The three-pane layout risks reading like generic developer tooling; the correction is profile-controlled density, outcome-first Everyday copy, a conversation-first center, and a right pane that appears only for selected context.
