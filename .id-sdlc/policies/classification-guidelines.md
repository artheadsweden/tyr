# Classification guidelines (ID-SDLC-Imp v0.1)

These guidelines help classify paths into zones in `id-sdlc-imp/.id-sdlc/zones.yml`.

Principles:
- Default to the stricter zone if unsure.
- Prefer inheriting classification from parent folders unless an override is needed.
- Use file-level overrides sparingly.
- Downgrades are allowed only for non-executable documentation files when the content cannot affect runtime behavior.

New folders:
- A new folder is treated as `yellow-auto` until explicitly classified.
- Review and assign an explicit zone to new folders within a reasonable timeframe.

Output expectations for agents:
- The intent agent records which zones are expected to be touched.
- If any red zone work or red operations are required, intent must say so clearly and propose a safe manual plan.
