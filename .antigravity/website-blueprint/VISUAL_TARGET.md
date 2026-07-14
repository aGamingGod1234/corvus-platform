# Visual Target

## Desired Emotional Effect

Corvus should feel calm enough for everyday work and exact enough for engineering work: a warm, trustworthy command space that explains what is happening and reveals deeper machinery only when the selected work style needs it.

## First Viewport Requirements

- First run immediately explains the current one-of-three setup choice and its consequence.
- Returning users see workspace name, Local or Cloud status, profile-specific navigation, and the most useful current work—not a generic dashboard grid.
- Everyday Personal is spacious and outcome-led; Developer Personal is denser and implementation-led.
- Team profiles include explicit ownership and scope labels and remain capability-gated until collaboration is real.
- Cloud Preview is visibly a preview with a Local fallback and no payment collection.

## Visual Hierarchy

1. Current workspace and the user’s next meaningful action.
2. Runtime/connection truth and any approval or recovery need.
3. Profile-specific work surface.
4. Contextual technical, owner, audit, or artifact detail.

## Motion Style

Selection tint, focused step transition, connection status, and inspector entry only. Use 160–280ms transitions and an immediate reduced-motion path. Live data updates should never cause layout jumps.

## Static Screenshot Success Criteria

- 1440x960 clearly shows the 240px rail, flexible main surface, and optional 360px inspector without crowding.
- 1024x900 preserves hierarchy with a collapsible inspector.
- 390x844 uses a compact top bar and bottom navigation rather than stacked desktop columns.
- Each of the four profiles is distinguishable by content, density, copy, and navigation while remaining unmistakably Corvus.
- The runtime choice and Cloud Preview cannot be mistaken for live E2B provisioning or checkout.

## Failure Conditions

- Generic SaaS cards dominate the viewport.
- Developer tool patterns are copied into Everyday views without translation.
- Personal and Team differ only by color.
- Mobile is a compressed desktop layout.
- Runtime, auth, sync, permissions, billing, or offline behavior is overstated.
