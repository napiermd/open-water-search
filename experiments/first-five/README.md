# The first five handoffs

Method fixed before this replay. The footage and full-queue results were already known. This is a retrospective comparison of recorded model decisions. It uses no API calls.

Give each method up to five possible-person handoffs per clip, in the production order (first seen). Use the same production grouping rule on each side. The detector keeps its recorded boxes with confidence at least 0.30. The Ember arm keeps the flags it accepted in the saved run. A handoff is scored at its actual last reported pin. A pin inside a previously unseen labeled track is a new person for that clip. Another handoff on that track is a repeat. A pin outside every labeled person is an empty alert. Unidentified person boxes are counted separately. A queue with fewer than five entries ends there.

Include all eight primary 24-second windows, including empty windows. Sum distinct people within each clip. Keep the two-minute demonstration flight separate. No changes to thresholds or ordering after scoring. This measures the contents of the first five messages, not how quickly a crew acts.

| Eight primary clips, seven labeled tracks | Messages opened | Distinct people | Repeats | Pins on empty water |
|---|---:|---:|---:|---:|
| Detector alone | 17 | 5 | 3 | 9 |
| Detector then Ember | 15 | 4 | 1 | 10 |

On the separate two-minute flight, the first five detector messages reached four of four labeled people with one empty alert. Ember reached three of four with two repeats and zero empty alerts. Detection and the check can change both the count of messages and their order. The two-minute flight had five detector messages available and eight Ember messages. Comparing first five therefore gives each method the same maximum number of opportunities.

The per-clip results, including empty clips and unused slots, are in [result.json](result.json). To reproduce locally with the saved queues and MOBDrone annotations:

~~~sh
python experiments/first-five/replay.py LOCKED_RUN WINDOWS.json MOBDRONE_PERSON_COCO.json FLIGHT_SCORING_DIR
~~~

The runner verifies queue and window hashes, uses the production handoff grouping code, and checks the two-minute Ember queue against the published record. Ground truth is used only for scoring. This is a descriptive result on previously used footage.
