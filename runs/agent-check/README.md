# Agent check: Ember choosing its own close looks, on the 30 validation photos

Ticket #7. The 30 SeaDronesSee validation photos ran as one flight with `--mode agent --budget 0.0192` on November 24, 2026. That is the same total spend the fixed method used in the format check (#5). Ember saw each overview and chose its close looks through three tools: look closer at a tile, report a sighting, and move to the next frame.

| 134 swimmers, equal spend | Found | Marks with no swimmer | Calls |
|---|---|---|---|
| Fixed method, grounding format (#5) | 79 | 13 | 90 |
| Agent mode (this run) | 54 | 11 | 51 |

The agent had to beat the fixed method at equal spend, so it did not become the default. Each tool-calling step resends the frame's conversation and the tool definitions, so the same money bought 51 calls instead of 90. 9 of the 30 photos never got a close look. Agent mode stays available with `--mode agent`.

Cost: $0.0178. The run stopped at its spending cap, as an equal-spend run should. `seal.json` holds the SHA-256 of the search record and calls log as written. The published copies have Meta's response and message IDs removed.
