# Open Water Search

Open Water Search helps a drone operator choose which sightings a boat crew should check first, then see exactly where the crew pointed back. A trained detector flags possible swimmers. Muse Ember checks the close-ups and helps decide which sightings to send.

[Try the 0:36 crew handoff](https://open-water-search.vercel.app/) · [Inspect the scored replay](https://open-water-search.vercel.app/pages/first-five.html) · [Download the audit](https://open-water-search.vercel.app/pages/first-five/audit.zip)

Built during the Muse Ember Hackathon, beginning November 23, 2026. [GitHub checks](https://github.com/napiermd/open-water-search/actions/workflows/tests.yml)

## What changed in the first five handoffs?

Both queues used the same recorded MOBDrone footage and simulated dispatch clock. Each could open up to five handoffs per 24-second window.

| Queue | In-water appearances reached | Empty handoffs |
| --- | ---: | ---: |
| Detector alone | 180 of 229 | 185 |
| Detector + Ember | **199 of 229** | **121** |

Across **129 windows from 42 recording families**, adding Ember reached **19 more in-water appearances** (+8.3 percentage points, paired 95% interval +3.7 to +13.3) and produced **64 fewer empty handoffs** (34.6% fewer, paired 95% interval 25.9% to 44.1%). Ember reached 23 appearances the detector queue missed and missed four the detector queue reached.

In flight 0015, both queues reached a swimmer in slot 2. The detector's fifth handoff was empty. With Ember, slot 5 reached another swimmer. [Detector slot 5](https://open-water-search.vercel.app/pages/first-five.html?video=DJI_0915_0015_50m.mp4&start=96&arm=detector&slot=5) · [Ember slot 5](https://open-water-search.vercel.app/pages/first-five.html?video=DJI_0915_0015_50m.mp4&start=96&arm=ember&slot=5)

The evaluation was retrospective. People can appear in multiple windows, some footage informed development, and the crew exchange is simulated. A pin marks a point in the image. Field testing with a rescue crew is an open question. The demo also shows a swimmer Ember dismissed at 0:12. [Demo](https://open-water-search.vercel.app/) · [Earlier results and failure cases](docs/results.md)

## How it works

~~~mermaid
flowchart LR
    footage["Drone footage"] --> detector["Detector flags possible swimmers"]
    detector --> ember["Muse Ember checks the close-ups"]
    ember -->|Kept| queue["Ranked handoffs with source frames"]
    ember -->|Dismissed| reopen["Crops stay available for review"]
    queue --> crew["Crew opens saved handoff and marks who they see"]
    crew --> operator["Operator compares the returned pin"]
~~~

Ember checks crops online through the Meta Model API. The crew can open the saved handoff and place a pin offline. The operator can open the returned reply on the original frame. One recorded two-minute flight checked **115 spots in 57 seconds for $0.008 in Ember usage**. [Run record and saved replies](runs/live-detector-check/README.md)

## Verify or run it

**Audit the 129 windows.** Unzip the [audit download](https://open-water-search.vercel.app/pages/first-five/audit.zip) and run `python3 -I verify.py` in the extracted folder. It checks the exact scored frames, pins, and order of all 838 handoffs and recomputes the comparison and confidence intervals. It runs offline with Python 3.

**Replay the two-minute flight.** From the repo root, install the [requirements](requirements.txt) and use the exact clip described in the [replay instructions](runs/live-detector-check/README.md#offline-flight-replay). The command uses saved detector boxes and 99 recorded Ember replies at $0 in new charges.

~~~sh
python3 runs/live-detector-check/replay_flight.py /path/to/clip.mp4 results/offline-flight
~~~

Open `results/offline-flight/report.html` to inspect the queue. For a new flight, follow the [detector setup and budgeted run instructions](docs/reproduce.md#run-it-on-your-own-flight). The command accepts a video or a folder of frames.

## Credits

The application code is [MIT](LICENSE). The separate [detector runner](detector/README.md) uses AGPL-3.0. The repository includes selected replay frames, resized crops, annotations, and records. See [imagery credits and data sources](docs/imagery-credits.md) and the [experiment history](docs/history.md).
