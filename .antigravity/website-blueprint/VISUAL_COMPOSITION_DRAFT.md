# Visual Composition Draft

## First Viewport Composition

The shell uses three stable zones: a 240px navigation rail with wordmark, workspace switcher, and profile-specific routes; a flexible content surface with a compact context/status header; and an optional 360px contextual inspector. A thin flight-path line can connect active progress or activity, but it must represent real state. The primary work surface changes composition by profile rather than filling the screen with interchangeable cards.

On first run, replace the shell with a centered, max-width setup field: step count and “Change anytime” eyebrow, one serif heading, one supporting sentence, two large semantic radio choices, and restrained Back/Continue actions. Runtime step uses full text labels beside local/computer and sourced cloud iconography.

## Spacing And Typography

Use existing Corvus tokens. Everyday surfaces use more vertical breathing room, sentence-case headings, and Fraunces for a few high-value page moments. Developer surfaces tighten row density and use IBM Plex Mono for repository, ID, branch, log, diff, and environment metadata. Inter Tight remains the primary UI face.

## Profile Differences

- Everyday Personal: cobalt accent, Today-led narrative, progress and outcomes.
- Developer Personal: cobalt accent, repository-led split pane, change/check density.
- Everyday Team: teal accent plus owner labels, assigned work and approval flow.
- Developer Team: teal accent plus explicit policy/audit context, queue and review density.

## Motion Timeline

At setup, the selected card settles in 160ms; Continue replaces the step in 160ms and focuses the next heading. In the shell, route selection and affected live rows tint in 160ms. Inspector enters in 280ms and restores focus on close. Reduced motion removes translation and cross-fade.

## Mobile Simplification

At 390x844, navigation becomes a compact top bar plus four primary bottom items and More. Workspace/project context opens as a drawer. Inspector becomes a full-screen dialog with a persistent close control and Escape support. Keep runtime status beside the workspace name; never place the entire desktop rail above content.

## Failure Conditions

Avoid glassmorphism, decorative dashboards, fake data, color-only role meaning, dense engineering controls in Everyday views, hidden Local/Cloud truth, or layout shifts during connection updates.
