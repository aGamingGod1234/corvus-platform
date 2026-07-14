# Corvus Operator Console Craft Brief

## Subject and job

Corvus is a local-first operations console for technical operators. Its one job is to make durable workflow state legible and let an operator take a governed next action without losing execution context.

The website-design-blueprint protocol is applied through the local `AGENT_USAGE.md`. The `impeccable` and `design-motion-principles` skills are unavailable in this session; their required craft and motion concerns are covered by the available `frontend-design` skill and this packet.

## Direction

- Scene sentence: a flight recorder opened on a calm engineering desk, with every transition attributable and every intervention deliberate.
- Viewer intent: find the active outcome, understand what is blocked, advance or approve it, then inspect governed project operations without losing the authority boundary.
- Signature: the execution rail, a continuous dependency line whose nodes show durable state and open the right-side inspector.
- Maximum generic cards: 3. The implementation uses 0; bordered rows, rails, and one inspector panel carry the hierarchy.
- Anti-patterns: marketing hero, metric strip, identical card grid, decorative charts, fake activity, gradient text, and hidden critical state.

## Tokens

- Paper `#f3f5f2`; raised paper `#ffffff`; ink `#182330`; muted `#68747e`; signal blue `#2f6fed`; approval amber `#c96c1a`; success green `#287a5b`; line `#d8dedb`.
- Display: Fraunces, limited to the Corvus wordmark and outcome heading.
- Body: Inter Tight for controls and explanatory copy.
- Utility: IBM Plex Mono for identifiers, state, budget, timestamps, and event sequence.
- Layout: 248px project rail / flexible execution canvas / 340px inspector on wide screens; a single stacked canvas with an overlay inspector below 900px.

resolvedThemeId: editorial-restraint
typographyLaneId: editorial-serif-grotesk
display: Fraunces
body: Inter Tight
motion lanes used: snappy, graceful, theatrical
anchorRefs:
- https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows
- https://vercel.com/geist/stack
- https://vercel.com/geist/sheet

## Source application

- `docs-github-com`: workflow, run, job, and step hierarchy informs the outcome/workflow/work-item vocabulary; no GitHub layout or copy is reproduced.
- The operations register reuses that legible runbook hierarchy for teams, provider references, memory, skills, routines, and signed ingress status.
- `vercel-com`: disciplined contrast and typography inform the token system; no Vercel brand treatment is reproduced.
- `vercel-com-2`: a right-side sheet informs the selected-work-item inspector, including explicit close, Escape handling, and focus return.
- `shadcn-button` / `tremor-button`: button state, focus, disabled, and loading patterns are adapted into local CSS without importing their styling systems.
- `lucide-activity` and `lucide-play`: source-backed icon paths are used with text labels and `aria-hidden` SVGs.

## Motion and accessibility

- Snappy (160ms): button and row state feedback.
- Graceful (280ms): inspector entrance and focus return.
- Theatrical is reserved and intentionally unused in the product surface despite being named in the tool contract.
- Live SSE changes briefly tint the affected rail node. Nothing loops continuously.
- `prefers-reduced-motion` removes translation and pulse while retaining immediate state-color changes.
- Every interactive row is a real button, focus is visible, status is not communicated by color alone, and the inspector has an explicit close action.

## Tool-contract applicability notes

The following v2.6 business-site terms are recorded for packet verification but are not product requirements for this authenticated application UI:

9_NON_NEGOTIABLE_v26_CONSTRAINTS
page-mode bilingual
reviews-min-star: 4
reviews-carousel-layout: side-by-side-centered
data-photo-id
photo-id-uniqueness-per-page
data-motion-trigger=text-reveal
data-motion-trigger=ambient-drift
data-typography-treatment=tint

Corvus contains no business reviews, Places imagery, marketing hero, or bilingual route contract, so those DOM patterns must not be fabricated.
