# First-five confirmation readiness

[GitHub #58](https://github.com/napiermd/open-water-search/issues/58) under [#55](https://github.com/napiermd/open-water-search/issues/55).

**Friday, November 27, 2026 — No-go today.** The inventory has **0 of 391** verified eligible swimmer-positive flights and **0 verified empty** flights. Keep confirmation open through **noon Pacific on Sunday, November 29, 2026** (20:00 UTC). The judge release proceeds on its own track. Use existing intake evidence during this window. This record authorizes zero model calls, footage acquisition, outreach, or spending.

## Evidence at this check

The workspace inventory at `work/motion-validation/source-inventory.csv` has 27 source rows. The `qualified_positive` and `qualified_empty` columns each sum to zero. Inventory SHA-256 is `1f3a3279bf270670b6580d9fcbe4341521181f46feb8de439300eb4ecb5c3bc4`.

- California has 81 beach-days with swimmer observations, with no verified takeoff-to-video mapping or references for the selected windows. Queensland logged 17,954 patrol flights, with the consecutive roster export, original footage access, and person references still unresolved.
- Previously used footage and duplicate views remain excluded. The other candidate sources lack some combination of unedited 24-second windows, verified takeoffs, exposure and actor checks, independent person references, or access.
- The local external first-five protocol and runbook under `outputs/water-probe/external-validation/` describe the paired study. Its default confirmation-mode scorer also requires at least 59 verified empty flights for its known-empty cohort. The protocol at `work/motion-validation/study/protocol.md` defines a separate 40-positive/59-empty motion study with its own endpoint.
- No qualifying roster, independently labeled windows, or capture, actor, and site-clustering review is available for the paired study. The existing scorer and runbook describe the mechanics. A roster-specific execution plan, end-to-end runtime through scoring by the Monday, November 30 freeze, and separately approved cost are still missing.

## Decision at the cutoff

**Go only if all of the following are in hand by noon Pacific:**

1. A fixed eligible roster supports 80% power for a true five-percentage-point reach gain. The planning estimate is 391 evaluable independent positive flights at 11.8% discordance. The scorer also requires at least 59 independently verified empty flights in its known-empty cohort. Verify unused capture provenance, takeoff IDs, actor reuse, and site clustering. Resolve material changes to discordance or independence with a prespecified sample size and analysis before viewing outcomes.
2. Independent, exhaustive references establish stable identities, physical settings, and full-frame boxes at each source second. For each eligible positive flight, select one in-water swimmer by the protocol's fixed draw in one prespecified, unedited 24-second window at 1 Hz.
3. An executable plan can deliver both arms, score them, and verify the results before Monday's freeze. It identifies the frozen detector checkpoint and threshold, Ember model and crop checks, ranking and updates, matched simulated clock, five opening slots, scoring, and terminal failure handling. Any paid execution has separate explicit authorization for the exact roster, request count, and hard cost cap.

**If any requirement is missing at the cutoff, close confirmation for this submission** and record the missing evidence. Keep the retrospective comparison for the submission, with development overlap and the simulated clock disclosed and the headline matched to the replay that ships under #55.

If every requirement is met and execution is separately authorized, seal the roster, references, both policies, clock, slots, and scoring before either arm's outputs are seen. Run once and report either outcome. Count only valid delivered openings and retain enrolled failures in the denominator. Report paired reach, its 95% interval, detector-only losses, identity switches, and the empty-opening trade-off. Primary success requires an observed reach gain of at least three points and a favorable two-sided exact McNemar result at 5%. Test empty-opening reduction only after primary success. A fresh dual-benefit claim also requires the paired 95% interval for empty-opening improvement to exclude zero in the favorable direction.
