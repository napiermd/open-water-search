# Format check: Meta's grounding format on the 30 validation photos

Ticket #5. The 30 SeaDronesSee validation photos ran as one flight with `--format grounding --looks 2 --budget 0.07` on November 24, 2026. Close looks asked for points on Meta's 0–1,000 grid, with structured output forcing a JSON schema. Overviews used the frozen ranking prompt.

| 134 swimmers | Pass rule | Result |
|---|---|---|
| Found with one close look | at least 63 | 69 |
| Found with two close looks | at least 74 | 79 |
| Marks with no swimmer, two close looks | at most 24 | 13 |

It passed, so the grounding format became the default. The published one-zoom tables stay tied to the frozen prompts. This is a separate run with its own overviews.

Cost: $0.0192 for 90 calls. `seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed. Crops and frames are left out because they are dataset images.
