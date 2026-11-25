# Open Water Search

A trained detector flags possible swimmers in every second of a drone flight, and Ember checks each flag. A reviewer, and through them a crew, receives the possible people with Ember's words, the flags it dismissed, and the water nobody has checked.

## Language

**Swimmer appearance** — One labeled swimmer in one photo. The same person can appear in several photos.

**Overview** — A reduced image of the whole frame, at most 1,000 pixels on its long edge, that Ember uses to choose where to zoom. Each overview is one paid look.

**Close look** — A magnified view of one tile. It gives the reviewer an opportunity to spot swimmers in that part of the water.

**Fixed grid** — A search that follows a predetermined tile order. Its starting tile advances one position for each successive frame.

**Swimmer in view** — A swimmer appearance whose labeled center lies in a tile selected for a close look. Each appearance counts once per search.

**Find** — A reported point that matches a published swimmer box. Each box can credit one point in each search.

**Blind crop review** — A reviewer marks possible swimmers in a close look while the search that selected it and the published labels are hidden. Someone who has seen the water before may still recognize it.

**Shared crop** — The same tile of the same frame selected by both searches. One blind response supplies the sightings for both.

**Judge’s extra look** — A close look the judge opens after stopping a recorded search at a chosen budget. It belongs to the judge’s exploration and carries no credit in the recorded search.

**Uninspected water** — The portion of a frame outside all completed close looks. A swimmer can remain there even when every inspected tile looks empty.

**Flagged crop** — A close look Ember sends to the reviewer with a possible swimmer location.

**Review decision** — A reviewer's judgment about a flagged crop. The reviewer can mark a swimmer, dismiss the flag, or leave it unresolved. Each decision leaves the search available to continue.

**Model coverage** — Water Ember inspected in a completed close look.

**Human review** — Water a person opened and reviewed. A tile can appear in model coverage while still awaiting human review.

**Matching pin** — The receiving reviewer's independently placed mark inside the reference box of the swimmer the sender indicated.

**Reviewer queue** — The short ranked list of flagged crops a search returns for a person to check. Each entry costs reviewer time whether or not it holds a swimmer.
_Avoid_: findings list, short list, results

**Coverage map** — A frame-by-frame record of which tiles received model coverage, which received human review, and which remain uninspected water.
_Avoid_: unchecked-water map, heat map

**Scale run** — One pass of the search over every photo in a split, rather than a 30-photo sample. It reports swimmers found, misses, false marks, cost and processing time.
_Avoid_: big run, full run

**Grounding format** — Meta's documented way for a model to report where something is: points or boxes on a 0–1,000 grid over the image it received.
_Avoid_: native coordinates, Meta coordinates

**Trained detector** — A conventional object detector trained on labeled SeaDronesSee photos. It makes the first pass over every frame, and it is also the comparison a judge expects.

**Flag** — One spot the trained detector marks as a possible swimmer.

**Ember's check** — Ember's answer about one flag, seen in a small crop around it: whether a person in the water is at its centre, how sure it is, and in a few words what is there. A flag Ember accepts is *kept*. One it turns down is *dismissed* and stays visible for a person to reopen.

**False alarm** — A kept mark with no labeled person under it. A second mark on a person already found also counts, and any stated number of false alarms gives that split.

**Unseen footage** — Drone frames from a source the trained detector never trained on, used to test whether either approach carries over to new cameras and water.
_Avoid_: out-of-distribution data, new data

**Spending cap** — The most a run may spend on Ember. A run stops itself before any request could cross it.
_Avoid_: budget limit, ceiling

**Flight** — The footage from one drone sortie, as a video or as photos in time order. It is the unit the tool searches.
_Avoid_: batch, folder, upload

**Search record** — What the tool returns for a flight: the possible people, the coverage timeline and a handoff message for each possible person.
_Avoid_: report, analysis, results

**Possible person** — One or more sightings in consecutive seconds that the tool treats as the same person in the water.
_Avoid_: detection, hit, target

**Coverage timeline** — For each second of a flight, which water received a close look and which remains uninspected water.
_Avoid_: heat map, search log

**Handoff message** — A short fixed-format message about one possible person that a dispatcher can read to a rescue crew.
_Avoid_: alert, summary, notification
