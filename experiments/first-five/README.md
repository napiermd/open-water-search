# The first five handoffs

Method fixed before this replay. The footage and full-queue results were already known. This is a retrospective comparison of recorded model decisions. It uses no API calls.

Give each method up to five possible-person handoffs per clip, in the production order (first seen). Use the same production grouping rule on each side. The detector keeps its recorded boxes with confidence at least 0.30. The Ember arm keeps the flags it accepted in the saved run. A handoff is scored at its actual last reported pin. A pin inside a previously unseen labeled track is a new person for that clip. Another handoff on that track is a repeat. A pin outside every labeled person is an empty alert. Unidentified person boxes are counted separately. A queue with fewer than five entries ends there.

Include all eight primary 24-second windows, including empty windows. Sum distinct people within each clip. Keep the two-minute demonstration flight separate. No changes to thresholds or ordering after scoring. This measures the contents of the first five messages, not how quickly a crew acts.
