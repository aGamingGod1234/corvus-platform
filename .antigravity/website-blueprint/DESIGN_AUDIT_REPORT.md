# Design Audit Report

- Generated: 2026-07-14T17:18:53.614571+00:00
- Project root: `C:\Users\lucas\Desktop\Projects\corvus-platform-main-integration`
- Verdict: `pass` (human-scored fixed-viewport review)

## Fixed Viewport Evidence
- Desktop: 1440x1000 before/after
- Tablet: 1024x900 before/after
- Mobile: 390x844 before/after
- Motion evidence: `.antigravity/website-blueprint/screenshots/after/after-browser-evidence.json`

## Section Provenance

### onboarding

- `github-com`
  - Visible influence to verify: direct business/domain positioning
  - Deliberately not copied: exact layout or private details
  - Screenshot proof: must be confirmed in visual audit.
- `linear-app`
  - Visible influence to verify: conversion flow and CTA pattern
  - Deliberately not copied: exact copy or brand-specific claims
  - Screenshot proof: must be confirmed in visual audit.
- `lucide-cloud`
  - Visible influence to verify: cloud interface icon source
  - Deliberately not copied: decorative icon use without semantic label
  - Screenshot proof: must be confirmed in visual audit.
- `shadcn-tabs`
  - Visible influence to verify: shadcn tabs implementation source and API shape
  - Deliberately not copied: incompatible imports or dependency changes without declaration
  - Screenshot proof: must be confirmed in visual audit.
- Custom UI constraint: Corvus needs three product decisions before it can load the correct runtime and information architecture.

### adaptive-shell

- `github-com`
  - Visible influence to verify: direct business/domain positioning
  - Deliberately not copied: exact layout or private details
  - Screenshot proof: must be confirmed in visual audit.
- `github-com-2`
  - Visible influence to verify: visual quality bar and composition pattern
  - Deliberately not copied: protected brand assets or exact creative
  - Screenshot proof: must be confirmed in visual audit.
- `linear-app`
  - Visible influence to verify: conversion flow and CTA pattern
  - Deliberately not copied: exact copy or brand-specific claims
  - Screenshot proof: must be confirmed in visual audit.
- `shadcn-tabs`
  - Visible influence to verify: shadcn tabs implementation source and API shape
  - Deliberately not copied: incompatible imports or dependency changes without declaration
  - Screenshot proof: must be confirmed in visual audit.
- Custom UI constraint: Different users need distinct language and density while sharing one domain and permission model.

### runtime-gate

- `github-com-2`
  - Visible influence to verify: visual quality bar and composition pattern
  - Deliberately not copied: protected brand assets or exact creative
  - Screenshot proof: must be confirmed in visual audit.
- `linear-app`
  - Visible influence to verify: conversion flow and CTA pattern
  - Deliberately not copied: exact copy or brand-specific claims
  - Screenshot proof: must be confirmed in visual audit.
- `lucide-cloud`
  - Visible influence to verify: cloud interface icon source
  - Deliberately not copied: decorative icon use without semantic label
  - Screenshot proof: must be confirmed in visual audit.
- Custom UI constraint: The current desktop sidecar is Local-only, so Preview must be visually useful without claiming a Cloud connection.


## Command Checks
- No package checks were available or checks were skipped.

## MCP Static Audit
```
onicGradients": 0,
      "totalGradients": 0,
      "distinctGradientTypes": 0,
      "mixBlendCount": 0,
      "filterCount": 0,
      "duotoneOrHalftone": false,
      "imageHoverColorTreatment": {
        "baseDesaturationCount": 0,
        "hoverColorRuleCount": 0,
        "weakDesaturationRules": [],
        "decisiveImageHoverTreatmentOk": true
      },
      "weakImageDesaturationCount": 0,
      "weakImageDesaturationRules": [],
      "photoIds": [],
      "photoIdsExceptLogo": [],
      "placesBusinessPhotos": [],
      "duplicatePhotoIds": [],
      "imgWithoutPhotoIdCount": 0,
      "imgWithEmptyAltAndNoId": 0,
      "imgFromStockCdn": 0,
      "imgFromAiGen": 0,
      "placesAttributionRendered": false,
      "cardSectionsHtmlCount": 0,
      "cardSectionsWithoutImg": 0,
      "reviewCardsTotal": 0,
      "reviewCardsBelow4": 0,
      "reviewCardsWithoutPhoto": 0,
      "visibleSrCopyOutsideSrOnly": 0,
      "viewAllCtaCount": 0,
      "heroAnimationPatternsPresent": [],
      "backgroundMotionPatternsPresent": [],
      "reviewsFlowPatternsPresent": [],
      "reviewsCarouselRoot": false,
      "reviewsTrackHorizontal": false,
      "reviewsTrackVerticalSuspect": false,
      "reviewsHasFocusedCard": false,
      "htmlLang": "en",
      "hreflangTags": [],
      "hreflangXDefault": false,
      "hreflangPair": false,
      "langToggleLinks": 0,
      "langToggleButtonsBad": 0,
      "siblingLanguageInDom": false,
      "stackedLangSpans": 0,
      "cjkCharCount": 0,
      "latinWordCount": 3,
      "headerNotFullyTranslated": false,
      "headerOppositeLatinCount": 0,
      "headerOppositeCJKCount": 0,
      "heroImgFirst": null,
      "serviceCardImgIds": [],
      "serviceCardReusesHero": null,
      "serviceCardsHaveServiceKey": false,
      "desaturatedDefaultOnShowcase": false,
      "heroLetterboxRisk": false,
      "heroImgPresent": false,
      "heroHasObjectCover": false,
      "heroTextOverImageNoScrim": false,
      "motionDefaultHidden": false,
      "motionBootstrapNoFallback": false,
      "motionStartingStyle": false,
      "motionNoscriptGuard": false,
      "carouselTeleportRisk": false,
      "reviewAvatarImgsCount": 0,
      "reviewAvatarsWithoutFallback": 0,
      "galleryImgCount": 0,
      "galleryUniformAspect": true
    }
  },
  "craftPassing": false,
  "craftPriorityFixes": [
    "[typography-distinctiveness] font-families: ≥2 distinct font-family declarations loaded",
    "[typography-distinctiveness] font-weights: ≥3 distinct font-weight values applied",
    "[typography-distinctiveness] stylistic-features: ≥1 of: stylistic-set (ss01..ss09), font-variation-settings, italic, opsz",
    "[typography-distinctiveness] letterspacing-curve: letter-spacing varies by size (not '0' on every heading)",
    "[typography-treatment-richness] hero-h1-multi-treatment: Hero h1 has ≥2 spans with distinct data-typography-treatment values",
    "[typography-treatment-richness] italic-or-weight-or-family: ≥1 emphasis treatment used somewhere on the page (italic OR weight-shift OR family-swap)",
    "[color-depth-state-derivation] color-mix-usage: ≥1 color-mix( occurrence in CSS",
    "[color-depth-state-derivation] derived-states: ≥4 distinct derived states (hover, focus, active, subtle, elevated, …)",
    "[color-depth-state-derivation] oklch-or-lab: colors expressed in oklch / lab / hsl with derivation, not raw hex only",
    "[color-depth-state-derivation] semantic-status: success/warning/danger semantic colors distinguished from brand accent",
    "[color-treatment-variety] ambient-gradient-present: ≥1 radial-gradient OR conic-gradient OR mesh-gradient as ambient depth",
    "[color-treatment-variety] gradient-variety: ≥2 distinct gradient declarations (linear + radial, or different stops)"
  ],
  "craftRuleSource": "rules/craft-scorecard.json",
  "04_HINT": "Pass project_root arg to auto-write DESIGN_SCORECARD_RESULT.json + DESIGN_AUDIT_REPORT.md to the packet (overwriting the legacy v1.0 outputs)."
}
```

## Diff Enforcement
- Diff enforcement passed or had no changed files.

## Issues
- No blocking visual issues after fixed-viewport and interactive browser review.
- Automation limitation: the static audit reads `apps/web/dist/index.html` without executing the SPA, so runtime-only `shadcn-tabs` and `lucide-cloud` markers were verified in source and Playwright-rendered UI instead.

## Human Scorecard
- Visual impact: 8/10
- Source alignment: 8/10
- Brand fit: 9/10
- Conversion clarity: 9/10
- Mobile polish: 8/10
- Motion taste: 8/10
- Genericness penalty: 1/10
- Evidence and critiques: `DESIGN_SCORECARD_RESULT.json`
