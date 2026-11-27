# First Five archive audit

Extract the entire download and run `python3 -I verify.py` in the extracted folder. The verifier needs only Python 3. It checks the replay and prints counts and 95% intervals as JSON. No credentials, network, model calls, or raw MOBDrone footage are required. The ZIP contains the same `replay.json` bytes served by the interactive replay.

The verifier checks the ordered 129-window roster and every scored opening in both arms against independent sealed evidence. The reference was extracted directly from the earlier water-statistics kit's original `primary-audit.json` and `paired-grades.csv` at their published SHA-256 values. It was never generated from the public replay. The verifier pins the reference hash and checks each slot's arm, order, source video and second, exact pixel pin, simulated opening time, queue identity, Ember-check status, reference match, and identity-switch count. It also checks each window's setting grades. For example, changing a pin or swapping two openings fails even when every aggregate stays the same. The trust anchor is the verifier from this release.

## How to read the comparison

Both arms use the same matched simulated dispatch clock and at most five openings per 24-second window. Each opening identifies the source recording, zero-based native frame number, sampled second, and SHA-256 of the JPEG the detector scored. The verifier looks up each opening in the original detector input manifest bundled as `detector-inputs.json` and checks its pinned checksum. To reproduce the JPEGs, run the extraction in `experiments/lost-people/flight-ranking/cut_flights.py` on the MOBDrone originals. For flight 0014, sample 2 is native frame 74 and sample 16 is native frame 494. The simulated dispatch clock is elapsed time from the start of that window. Windows can have fewer than five openings.

The replay reaches a labeled track when an opening pin lands on it. A later opening on that same track in the window is a repeat. An opening without any matching labeled track is empty. A match outside the water still occupies a slot. Reach and its paired breakdown count distinct tracks graded in water, once per window. The setting grades were assigned retrospectively. The same person can appear in multiple windows. Identity switches are the original tracking audit's per-card counts across opening and follow-up pins, reported separately from opening outcomes.

The result covers 229 in-water appearances across 129 windows and 42 recording families. The archive overlaps development and dispatch was simulated. The original comparison used the saved Muse Ember 1.0 outputs from Meta Model API and the SeaDronesSee-trained YOLO26m detector. The offline verifier replays the saved record and uses the original 20,000 family resamples, drawn in sorted family order with NumPy's `default_rng(20261126).multinomial`. It recomputes both arms' paired outcomes in each resample and uses the 2.5th and 97.5th percentiles. The bundled resampling weights let the verifier reproduce the original intervals with standard-library Python.

## Flight 0014 and release fallback

For the opening 24 seconds of `DJI_0804_0014_50m_2.mp4`, both arms reached tracks 6 and 17. The grading labels track 17 **On shore**. Ember also reached track 0, and the detector also reached track 1. Each arm reached **two in-water tracks and three labeled tracks total**, with **two empty openings in five slots**. This corrects the case-level in-water count in #57. The archive headline reproduces exactly. If the release rehearsal surfaces any replay mismatch, use the audited headline for the flow that passes, as directed by #55.

The signed-out archive route is `/pages/first-five.html`. From #57's flight 0014 interaction, link to `/pages/first-five.html?video=DJI_0804_0014_50m_2.mp4&start=0`. For the two case openings, append `&arm=ember&slot=4` (track 0) or `&arm=detector&slot=5` (track 1).

## Rebuild from the sealed inputs

From the repository root, run `python3 runs/first-five-audit/build.py /path/to/outputs/water-probe` with NumPy installed. The builder reads the local detector-control audit and paired setting grades for the replay. It reads the previous `share/water-statistics/audit.zip` separately to create the reference. It checks the original source seals before exporting either and verifies that the new reference matches the pinned verifier hash. Run `python3 -m unittest discover -s runs/first-five-audit` to exercise the downloaded verifier against the public records.
