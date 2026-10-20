# AGENTS.md

## Code Style
- Write code like a senior engineer teaching a junior developer. Keep the codebase approachable without unnecessary bloat.
- Prefer simple, explicit syntax over clever or complex abstractions.
- Add abstractions only when they remove real complexity or match an established local pattern.
- Keep simple local boolean checks in the function rather than extracting tiny helpers.

## Development and validation
- This is an experimental game-control and RL project. Prefer writing code, checking behaviour in the game, inspecting logs and iterating.
- Do not add automated tests unless the user explicitly requests them. Do not expand the suite as part of routine feature work.
- Existing tests can remain where they cover useful behaviour. Avoid tests that simply repeat static data or verify argument forwarding.
- Report what was actually observed in the game and what remains unverified. A mocked test is not live validation.
- Keep tensor and action complexity tied to a concrete policy decision and explain its economic or strategic purpose. Treat performance benefits as hypotheses until measured.
- Keep build and assign as separate policy actions. Build only places a site; after simulation advances, observations expose staffing and the policy can choose a separate assignment by profession and source zone. Do not combine them or schedule an automatic fallback assignment.
