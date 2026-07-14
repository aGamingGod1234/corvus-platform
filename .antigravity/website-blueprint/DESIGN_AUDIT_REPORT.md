# Design Audit Report

- Generated: 2026-07-14T13:38:37.579085+00:00
- Project root: `C:\Users\lucas\Desktop\Projects\corvus-platform`
- Verdict: `fail`

## Fixed Viewport Evidence
- Desktop: 1440x1000 before/after
- Tablet: 1024x900 before/after
- Mobile: 390x844 before/after
- Motion evidence: `.antigravity/website-blueprint/screenshots/after/after-browser-evidence.json`

## Section Provenance

### app-header

- `vercel-com`
  - Visible influence to verify: visual quality bar and composition pattern
  - Deliberately not copied: protected brand assets or exact creative
  - Screenshot proof: must be confirmed in visual audit.

### project-rail

- `docs-github-com`
  - Visible influence to verify: direct business/domain positioning
  - Deliberately not copied: exact layout or private details
  - Screenshot proof: must be confirmed in visual audit.

### execution-canvas

- `docs-github-com`
  - Visible influence to verify: direct business/domain positioning
  - Deliberately not copied: exact layout or private details
  - Screenshot proof: must be confirmed in visual audit.
- `lucide-play`
  - Visible influence to verify: play interface icon source
  - Deliberately not copied: decorative icon use without semantic label
  - Screenshot proof: must be confirmed in visual audit.
- `shadcn-button`
  - Visible influence to verify: shadcn button implementation source and API shape
  - Deliberately not copied: incompatible imports or dependency changes without declaration
  - Screenshot proof: must be confirmed in visual audit.

### detail-inspector

- `lucide-activity`
  - Visible influence to verify: activity interface icon source
  - Deliberately not copied: decorative icon use without semantic label
  - Screenshot proof: must be confirmed in visual audit.
- `shadcn-button`
  - Visible influence to verify: shadcn button implementation source and API shape
  - Deliberately not copied: incompatible imports or dependency changes without declaration
  - Screenshot proof: must be confirmed in visual audit.
- `vercel-com-2`
  - Visible influence to verify: conversion flow and CTA pattern
  - Deliberately not copied: exact copy or brand-specific claims
  - Screenshot proof: must be confirmed in visual audit.

### operations-canvas

- `docs-github-com`
  - Visible influence to verify: direct business/domain positioning
  - Deliberately not copied: exact layout or private details
  - Screenshot proof: must be confirmed in visual audit.
- `shadcn-button`
  - Visible influence to verify: shadcn button implementation source and API shape
  - Deliberately not copied: incompatible imports or dependency changes without declaration
  - Screenshot proof: must be confirmed in visual audit.


## Command Checks
- No package checks were available or checks were skipped.

## MCP Static Audit
```
s": 0,
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
      "htmlLang": null,
      "hreflangTags": [],
      "hreflangXDefault": false,
      "hreflangPair": false,
      "langToggleLinks": 0,
      "langToggleButtonsBad": 0,
      "siblingLanguageInDom": false,
      "stackedLangSpans": 0,
      "cjkCharCount": 0,
      "latinWordCount": 1871,
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
    "[typography-treatment-richness] section-h2-has-eyebrow: ≥80% of section h2s have a data-typography-treatment=eyebrow sibling",
    "[typography-treatment-richness] italic-or-weight-or-family: ≥1 emphasis treatment used somewhere on the page (italic OR weight-shift OR family-swap)",
    "[color-depth-state-derivation] color-mix-usage: ≥1 color-mix( occurrence in CSS",
    "[color-depth-state-derivation] derived-states: ≥4 distinct derived states (hover, focus, active, subtle, elevated, …)",
    "[color-depth-state-derivation] oklch-or-lab: colors expressed in oklch / lab / hsl with derivation, not raw hex only",
    "[color-depth-state-derivation] semantic-status: success/warning/danger semantic colors distinguished from brand accent",
    "[color-treatment-variety] ambient-gradient-present: ≥1 radial-gradient OR conic-gradient OR mesh-gradient as ambient depth"
  ],
  "craftRuleSource": "rules/craft-scorecard.json",
  "04_HINT": "Pass project_root arg to auto-write DESIGN_SCORECARD_RESULT.json + DESIGN_AUDIT_REPORT.md to the packet (overwriting the legacy v1.0 outputs)."
}
```

## Diff Enforcement
- Diff enforcement passed or had no changed files.

## Issues
- INTERACTION_SPEC.json must define a `dish-selector` interaction.
- Packet is not approved.
- Applied component source `shadcn-button` selector `.button--primary` is not present in HTML.
- Applied component source `lucide-activity` has no visible `data-component-source` usage in HTML.
- Applied component source `lucide-play` has no visible `data-component-source` usage in HTML.
- visualImpact is below 8/10.
- sourceAlignment is below 8/10.
- brandFit is below 8/10.
- conversionClarity is below 8/10.
- mobilePolish is below 8/10.
- motionTaste is below 8/10.
