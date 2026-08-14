# AI services (Phase 2+)

Independent service modules will live here:

- `product-analysis.ts` — product analysis agent
- `ad-concept.ts` — creative concept agent
- `image.ts` — `generateImage()` (provider-agnostic)
- `video.ts` — Remotion composition helpers

Do not call model APIs from UI components; always go through these services.
