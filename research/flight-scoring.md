# Scoring a drone search per person and per flight

Research date: 2026-11-24. Status: all four areas covered. Gaps are listed at the end under "Not verified".

Tags used:

- **[read]** I opened the document and read the passage.
- **[abstract]** I read the publisher or PubMed abstract only.
- **[search summary]** A search result quoted the primary page. I did not open the page.
- **[unverified]** Not checked against the owning source.
- **[inference]** My own reasoning from the sources.

## Answer

1. Rescue planning already scores a search per object and per sortie. IAMSAR defines probability of detection (POD) as the probability that the search object is detected, given that it was in the area searched. Images play no part in the definition. **[read]** https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf
2. The field experiments behind the sweep width tables record one detect-or-miss outcome for each object on each pass. Repeat sightings of the same object count once, and false detections are logged apart from the analysis. That is the "found at all" measure a crew expects. **[read]** https://www.dco.uscg.mil/Portals/9/CG-5R/nsarc/LandSweepWidthDemoReportFinal.pdf
3. Detection-system standards report three things together. They give a detection rate per real event, a time limit from the event to the alarm, and false alarms per unit of operating time. ISO 20380 for pool drowning detection asks for at least 80% detection, an alarm within 15 seconds, and at most five false alarms per day per basin. **[read]** https://cdn.standards.iteh.ai/samples/67857/66a010c70cd940dc963def72fa5773eb/ISO-20380-2017.pdf
4. Computer-vision benchmarks for people in water score per box. MOBDrone, HERIDAL and WiSARD report average precision, precision and recall per image. SeaDronesSee tracking reports HOTA, MOTA and IDF1. The only standard per-person measure in that family is "mostly tracked" and "mostly lost". None of the four reports time to first detection. **[read]** https://arxiv.org/abs/2203.07973 https://arxiv.org/abs/2309.04453 https://openaccess.thecvf.com/content/WACV2022/papers/Varga_SeaDronesSee_A_Maritime_Benchmark_for_Detecting_Humans_in_Open_Water_WACV_2022_paper.pdf https://arxiv.org/abs/1603.00831
5. A labelled video at one frame per second with a track identity per person supports a per-person, per-flight score directly. It cannot give sweep width, coverage factor or POD in the IAMSAR sense without the drone's position, height and camera angle. **[inference]**

Proposed score, four numbers per flight (definitions in section 6):

| # | Number | Plain reading | Machine-learning name |
|---|---|---|---|
| 1 | People found, k of n | Each labelled person counts as found if at least one mark lands inside their box at any time in the flight | Recall over ground-truth tracks |
| 2 | Time to first mark | Seconds from the first labelled frame of a person to the first mark inside their box. Report the median, the slowest, and the share found within 10 seconds | Track latency |
| 3 | False dispatches per flight hour | Episodes of marks on something that is no labelled person, merged when they run together, divided by flight time | Rate of false alarms |
| 4 | Contact held | For each found person, the share of their visible seconds that carried a mark. Report the mean and the count held for 80% or more | Detection recall per track, and mostly tracked |

## 1. Maritime search planning

| Measure | Definition | Source |
|---|---|---|
| Probability of detection (POD) | The probability of the search object being detected, assuming it was in the areas searched. It is a function of coverage factor, sensor, search conditions and how accurately the search pattern is navigated. The glossary adds that POD measures sensor effectiveness. | **[read]** IAMSAR Volume II glossary and chapter 4, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf |
| POD, Coast Guard wording | The statistical measure of search sensor detection performance. It is a conditional probability that assumes the object is in the search area, and a function of sweep width and track spacing. Cumulative POD over n searches is 1 − (1 − POD1)(1 − POD2)…(1 − PODn). The Addendum adds that cumulative POD has little meaning at sea because objects drift. | **[read]** US Coast Guard Addendum, COMDTINST 16130.2H, H.5.6.2, https://www.dco.uscg.mil/Portals/9/CG-5R/MassRescueOps/CGADD%20COMDINST%2016130_2H.pdf?ver=tYaRnfVEGQhBxk3HXkimww%3D%3D |
| Sweep width (W) | A measure of how well a given sensor detects a given object in given conditions. The chance of detecting an object farther than half a sweep width from the track equals the chance of missing one inside that distance. Values come from tables multiplied by correction factors. | **[read]** IAMSAR Volume II 4.6.7, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf |
| Sweep width, Coast Guard wording | The width of a swath centred on the search unit's track where the probability of detecting an object outside the swath equals the probability of missing one inside it, for uniformly distributed objects. It is less than twice the maximum detection range. | **[read]** Addendum Appendix H, https://www.dco.uscg.mil/Portals/9/CG-5R/MassRescueOps/CGADD%20COMDINST%2016130_2H.pdf?ver=tYaRnfVEGQhBxk3HXkimww%3D%3D |
| Sweep width, mathematical form | W = ∫ p(x) dx, the area under the lateral range curve p(x), where x is the closest distance between searcher track and object. | **[read]** J. R. Frost, "The Theory of Search", prepared with the US Coast Guard, 4.3.1, https://www.navcen.uscg.gov/sites/default/files/pdf/Theory_of_Search.pdf |
| Search effort (Z) | Z = V × T × W, search speed times search endurance times sweep width. Search endurance is usually taken as 85% of on-scene endurance, which leaves 15% for investigating sightings and turning. | **[read]** IAMSAR Volume II 4.6.8 and glossary, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf |
| Coverage factor (C) | C = Z / A, search effort divided by area searched. For parallel sweeps C = W / S, sweep width over track spacing. The Addendum also writes C = (W × V × T) / A and calls it a measure of search thoroughness. | **[read]** IAMSAR Volume II chapter 4, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf. **[read]** Addendum H.5.5, https://www.dco.uscg.mil/Portals/9/CG-5R/MassRescueOps/CGADD%20COMDINST%2016130_2H.pdf?ver=tYaRnfVEGQhBxk3HXkimww%3D%3D |
| POD from coverage | Read from two curves, ideal and normal conditions. IAMSAR worked examples pair C = 0.5 with 47%, C = 1.0 with 79% and C = 1.5 with 94%. The random-search form is POD = 1 − e^(−C). | **[read]** IAMSAR Volume II 4.6.14 and figures 4-17 to 4-20, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf. **[read]** Frost equation 5-7, https://www.navcen.uscg.gov/sites/default/files/pdf/Theory_of_Search.pdf |
| Probability of success (POS) | POS = POC × POD, where POC is the probability the object is in the area. IAMSAR says POS measures search effectiveness. | **[read]** IAMSAR Volume II glossary, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf |
| Person in water, weather | The weather correction factor for a person in water, raft or small boat drops to 0.5 in 15 to 25 knot winds and to 0.25 above 25 knots. | **[read]** IAMSAR Volume II Table N-7, https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf |

How the numbers behind these tables were measured:

- Since the late 1970s the Coast Guard Research and Development Center has anchored simulated people in the water, life rafts and small boats in a test area and sent search units through on set tracks. Each pass gives a detection or a miss at a known lateral range. Plotting detection probability against lateral range gives the curve, and its area gives the sweep width. **[read]** https://www.dco.uscg.mil/Portals/9/DCO%20Documents/Proceedings%20Magazine/Archive/2025/USCG_Proceedings-Magazine_Vol82-No1_Spring25-WEB.pdf **[abstract]** https://trid.trb.org/View/177235
- The written procedure for these experiments counts initial detections only. Several detections of one object by one searcher count as one detection. Passing an object without seeing it counts as one non-detection. False detections may be noted and are left out of the sweep width analysis. **[read]** Robe and Frost 2002, https://www.dco.uscg.mil/Portals/9/CG-5R/nsarc/LandSweepWidthDemoReportFinal.pdf

The unit of account in rescue practice is therefore one object on one pass, scored detected or missed. **[inference]**

## 2. Time to detection and false alarm rate in detection-system evaluation

| System | Detection | Time | False alarms | Source |
|---|---|---|---|---|
| Pool drowning detection, ISO 20380:2017 | Detection rate of at least 80% under the standard's test method, one alarm per detection | "Alarm set off time" runs from the moment a solid mass is fully immersed, on the pool bottom and stationary, until the alarm. It must be 15 seconds or less. | A false alarm is an alarm set off for a reason other than detection. The limit is an average of five per day per basin during public opening hours over 30 days. | **[read]** ISO preview copy, https://cdn.standards.iteh.ai/samples/67857/66a010c70cd940dc963def72fa5773eb/ISO-20380-2017.pdf |
| Man-overboard detection, ISO 21195:2020 | Clause 7.2 covers probability of detection. An operator reviews every event the system raises. | Not seen | A false alarm is a system activation with no actual man-overboard event. Clause 7.3 sets a false alarm rate. | **[read]** definitions and contents page, https://cdn.standards.iteh.ai/samples/76051/f00f5276aa6f46b4bc2254f3be4b4882/ISO-21195-2020.pdf. Thresholds **[unverified]**, behind the paywall |
| Man-overboard detection, Bureau Veritas rules | Manikin detection probability of 95% or more, from at least 100 drop tests | Image data at the control station within five seconds of an alert | False alerts averaged over 90 days must stay at or below four per day | **[read]** NR467 Part F, https://rulesexplorer-docs.bureauveritas.com/documents/nr467/jan2026/467-NR_PartF_2026-01.pdf |
| Marine radar, IMO MSC.192(79) | Detection means an indication of the target in at least 8 of 10 scans, at a false alarm probability of 10^-4. Tracking continues while the target is distinguishable in 5 of 10 scans. | "Range of first detection" in clutter is tested against a benchmark target | Set as the 10^-4 probability above | **[read]** https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf |
| Video analytics, UK Home Office i-LIDS | An alarm event is either detected or missed. Recall and precision combine into an F1 score. | The system has ten seconds from the start of the event to alarm. Later alarms count as false. | Bursts of false alarms are logged as one every five seconds. | **[read]** https://assets.publishing.service.gov.uk/media/5a7ac14d40f0b66eab99c6c0/ilids-user-guide.pdf |
| Activity detection in video, NIST ActEV | Pmiss = missed instances / true instances | None | RateFA = false alarms / video duration in minutes. Results are quoted as Pmiss at a fixed RateFA such as 0.15 per minute. | **[read]** https://actev.nist.gov/pub/Draft_ActEV_2018_EvaluationPlan.pdf |
| Surveillance event detection, TRECVID 2008 | Missed detection probability | None | False alarm rate per unit time. The two combine into the Normalized Detection Cost Rate. | **[read]** https://www-nlpir.nist.gov/projects/tv2008/index.html |
| Radar multi-target tracking | Track completeness, the share of live objects with a track on them **[search summary]** https://www.mdpi.com/1424-8220/22/3/793 | Track latency, the lag between a target appearing and a confirmed track on it | Rate of false alarms and ratio of spurious tracks | **[read]** Gorji, Tharmarasa and Kirubarajan 2011, on a third-party copy, https://www.academia.edu/64572036/Performance_measures_for_multiple_target_tracking_problems |
| Lifeguards, Ellis and Associates 10/20 | Scan the whole zone | Recognise a guest in distress within 10 seconds and reach them within 20 | None | **[read]** https://s3.amazonaws.com/moreyspiers.com/iltp-5th_edition.pdf |

Three conventions recur. **[inference]**

- The clock starts at a defined physical event (immersed and stationary, event start in the ground truth, guest in distress) and stops at the first alarm.
- Misses are counted on their own line and kept out of the time average. The DJI and EENA Drone Efficacy Study reports "not found" trials as missing values beside the time-to-locate figures. **[read]** https://eena.org/wp-content/uploads/2019/08/2018_09_18_EENA_DJI2Report19.pdf
- False alarms are divided by operating time, and bursts are merged so that one nuisance object counts once.

## 3. Computer-vision benchmarks and tracking measures

| Benchmark or measure | What it scores | Source |
|---|---|---|
| SeaDronesSee, paper | Multi-object tracking follows the MOT benchmark protocol and reports MOTA, IDF1, MOTP, false positives, false negatives, recall, precision, identity switches and fragmentations. The results tables also carry MT and ML columns. | **[read]** Varga et al., WACV 2022, section 5.3, https://openaccess.thecvf.com/content/WACV2022/papers/Varga_SeaDronesSee_A_Maritime_Benchmark_for_Detecting_Humans_in_Open_Water_WACV_2022_paper.pdf |
| SeaDronesSee, current benchmark | The multi-object tracking track lists HOTA, MOTA and IDF1. **[read]** https://www.macvi.org/dataset. The challenge page lists HOTA, MOTA, IDF1, MOTP, MT, ML, FP, FN, recall, precision, identity switches and fragmentations. **[search summary]** https://seadronessee.cs.uni-tuebingen.de/wacv23_SeaDronesSee_tracking | as cited |
| MOBDrone | AP50 and COCO mAP at IoU 0.50 to 0.95, F1 at IoU 0.5, and a true positive rate over person boxes. The authors treat AP50 as the most meaningful because detecting a person overboard matters more than a tight box. The paper has no tracking, per-person or timing measure. | **[read]** Cafarelli et al. 2022, https://arxiv.org/abs/2203.07973 |
| HERIDAL | Still images. About 68,750 training patches and about 500 labelled full-size test images. Reported as detection rate 88.9% and precision 34.8%. | **[abstract]** Božić-Štulić, Marušić and Gotovac, IJCV 2019, https://link.springer.com/article/10.1007/s11263-019-01177-1 |
| HERIDAL follow-up | Search-and-rescue experts and the detector are compared on mission image sets by precision, recall and inspection time per image. | **[read]** Gotovac et al. 2020, https://www.mdpi.com/2072-4292/12/20/3295 |
| WiSARD | Precision, recall, mAP at 0.5 and mAP at 0.5 to 0.95. The authors rank recall above precision because an operator can check a false detection quickly while a miss delays the rescue, and they treat a rough position as adequate. | **[read]** Broyles et al., https://arxiv.org/abs/2309.04453 |
| MOTA | 1 − Σ(FN + FP + IDSW) / ΣGT, summed over frames. Every box counts once. | **[read]** MOT16 paper, equation 1, https://arxiv.org/abs/1603.00831 |
| Mostly tracked, mostly lost | A ground-truth trajectory is mostly tracked (MT) if it is tracked for at least 80% of its life span, whatever identity the tracker assigns. It is mostly lost (ML) if tracked for less than 20%. Both are reported as a share of all ground-truth trajectories. Fragmentations count each break in tracking. | **[read]** MOT16 paper, 4.1.6, https://arxiv.org/abs/1603.00831 |
| IDF1 | 2·IDTP / (2·IDTP + IDFP + IDFN), after one best match between true and computed identities. | **[read]** Ristani et al. 2016, equation 11, https://arxiv.org/abs/1609.01775 |
| HOTA | HOTAα = sqrt( Σ over true positives of A(c) / (TP + FN + FP) ), the geometric mean of a detection score and an association score, averaged over localisation thresholds α. Its detection recall part is DetRe = TP / (TP + FN). | **[read]** Luiten et al. 2020, equation 13, https://arxiv.org/abs/2009.07736 |
| OWTA | sqrt(DetRe × AssA). It leaves false positives unpenalised. | **[read]** Liu et al., CVPR 2022, https://openaccess.thecvf.com/content/CVPR2022/papers/Liu_Opening_Up_Open_World_Tracking_CVPR_2022_paper.pdf |
| Track mAP | Average precision over whole tracks, matched by 3D IoU at 0.5. Tracking an object for a short time earns no partial credit. | **[read]** Dave et al., TAO, https://arxiv.org/abs/2005.10356 |

Notes:

- I found no standard measure named "track recall" in these sources. The nearest are MT and ML, and track-level matching in Track mAP. "Detected at least once per ground-truth track" is a simple special case that the benchmarks above do not report. **[inference]**
- MOTA, IDF1 and HOTA weight a person by the number of frames they are visible. A person in view for 300 seconds counts sixty times as much as one in view for 5 seconds, so a high score can sit alongside a short-lived person who was never marked. **[inference]**
- IDF1 and the association half of HOTA need the system to output its own track identities and boxes. A system that outputs point marks per frame has neither. **[inference]**

## 4. Drone search-and-rescue studies with per-victim detection or time to detection

| Study | Setting | What it reports | Source |
|---|---|---|---|
| Claesson et al. 2017 | Simulated drowning, submerged manikin | Median time from start to contact with the manikin was 4:34 min for the search party and 0:47 min for the drone system. | **[abstract]** https://pubmed.ncbi.nlm.nih.gov/28110000/ |
| Seguin et al. 2018 | Simulated swimmer in the sea, 28 tests | Time to deliver a flotation device was 81 ± 39 s by drone against 179 ± 78 s by standard rescue in moderate sea, and 99 ± 34 s against 198 ± 130 s in rough sea. | **[abstract]** https://pubmed.ncbi.nlm.nih.gov/29653153/ |
| Karaca et al. 2018 | Mannequin on snow, randomised simulation | Median time to arrival at the mannequin was 57.3 min for the classical technique and 8.9 min for drone plus snowmobile. | **[abstract]** https://pubmed.ncbi.nlm.nih.gov/28928001/ |
| Drone Efficacy Study, DJI, EENA and Black Channel 2018 | Randomised land search trials, 50 events | Primary endpoint is time to locate, started when the first team member moves to begin the search. Drone teams found the target in 23 of 30 trials and ground teams in 17 of 20. When drone teams found the target they were 191 seconds faster. | **[read]** https://eena.org/wp-content/uploads/2019/08/2018_09_18_EENA_DJI2Report19.pdf |
| "UAV-Based Visual Detection and Tracking of Drowning Victims in Maritime Rescue Operations", Drones 2026 | Near-shore sea flights with an on-board detector | Per scenario, seconds after take-off to first detection (50 s for a swimming person, 120 s for the first suspected drowning) and a "correct detection rate" from 84% down to 51%. | **[read]** https://www.mdpi.com/2504-446X/10/2/146 |
| Burke et al. 2019 | Thermal drone, coastal scenarios including a person in the water | A pilot study of whether volunteers can be picked out by eye and by a simple automated detector. The authors accept a few false positives as long as nobody is missed. | **[read]** https://researchonline.ljmu.ac.uk/id/eprint/11583/1/SAR_Published.pdf |
| Doherty and Rudol 2007 | Two autonomous helicopters, 290 × 185 m area | Eleven bodies placed in the area and a mission of about ten minutes. I did not confirm the per-body result. | **[read]** on a third-party copy, https://studylib.net/doc/27060900/a-uav-search-and-rescue-scenario-with-human-body-detectio... |
| Niedzielski et al. 2018 | Field experiment with people simulating being lost | Reports the time to find the lost person. I saw only fragments of the text. | **[unverified]** https://onlinelibrary.wiley.com/doi/10.1002/rob.21784 |
| Goodrich et al. 2008 | Mini drone field trials with a county search team | Lessons on video presentation and team integration. No per-victim figures confirmed. | **[abstract]** https://onlinelibrary.wiley.com/doi/10.1002/rob.20226 |

Two gaps. I found no published sweep width or lateral range curve for a drone searching for a person in the water. I found no study that reports false alarms per flight hour for a drone person detector at sea. One search round each, so absence here is weak evidence. **[unverified]**

## 5. What a labelled 1 FPS video with track identities can support

| Measure | Supported | Condition or limit |
|---|---|---|
| Found or missed, per person per flight | Yes | Needs a matching rule (mark inside the person's box) and the track identity to group frames. |
| Time to first detection | Yes, to the nearest second | The clock starts at the first labelled frame. That is the moment a labeller could see the person, which may be later than the moment the person entered the camera footprint. |
| False alarms per flight hour | Yes | Flight time is the frame count in seconds. Needs a merging rule so one floating object held in view counts once. |
| Mostly tracked, mostly lost, per-track recall, fragmentations | Yes | One sample per second is enough because the thresholds are shares of the life span. |
| MOTA | Partly | Computable as 1 − (FN + FP) / GT with point-in-box matching. The identity-switch term needs system track identities. |
| IDF1, HOTA association, Track mAP | No | They need the system to output track identities and boxes. |
| Localisation accuracy (MOTP, IoU thresholds) | No | A point mark has no extent. |
| Sweep width, lateral range curve, coverage factor | No | They need each person's distance from the drone track, so drone position, height and camera angle per frame, plus area and track spacing. |
| POD in the IAMSAR sense | No | POD is conditional on the person being in the area searched. The labels cover only people who appeared in frame and whom a labeller saw. The honest name for number 1 is "found rate among labelled people". |
| Delays under one second, or people visible for under one second | No | Sampling limit. |

Two limits on precision. **[inference, standard binomial and Poisson arithmetic, no source consulted]**

- If all n labelled people are found, the 95% lower bound on the found rate is 0.05^(1/n). That is 74% for 10 people, 90% for 30 and 95% for 59. Bureau Veritas asks for at least 100 drops before accepting a 95% claim. **[read]** https://rulesexplorer-docs.bureauveritas.com/documents/nr467/jan2026/467-NR_PartF_2026-01.pdf
- With zero false dispatches in T hours, the 95% upper bound is about 3 / T per hour. MOBDrone holds 126,170 frames at 30 FPS according to the project's earlier note, about 70 minutes, so it can show at best "under about 2.6 per hour". **[unverified this pass]** https://zenodo.org/api/records/5996890

## 6. Proposed score

Scoring rules:

- A flight is one continuous clip. Flight time is its length in seconds.
- A mark matches a person when it lands inside that person's labelled box in that frame.
- Labelled objects that are neither a target nor a false alarm (people on boats, for example) are set aside from both counts. MOT16 does the same with an "ignore" flag on some annotated instances. **[read]** https://arxiv.org/abs/1603.00831
- Fix the operating point before scoring: the confidence threshold and the cap of five marks per photo.

The four numbers:

1. **People found, k of n.** A labelled person is found if at least one mark matches them in any frame of the flight. Report the count per flight. Pool across flights for a rate with an interval.
2. **Time to first mark.** For each found person, the seconds from their first labelled frame to their first matched mark. Report the median, the slowest, and the share of all n people found within 10 seconds. A person never found counts against the 10-second share and stays out of the median.
3. **False dispatches per flight hour.** A false mark is a mark that matches no labelled person and falls in no set-aside region. Consecutive seconds with a false mark form one episode, and episodes less than five seconds apart are merged. Report episodes per flight and episodes per hour pooled across flights. Where a false mark lands inside a labelled non-person object that has its own track identity, count that object once.
4. **Contact held.** For each found person, matched seconds divided by visible seconds. Report the mean across found people and the count at 80% or more.

Why a rescue professional would accept them:

- Number 1 uses the detection experiment rule. One object, one pass, detected or missed, with repeat sightings counted once. **[read]** https://www.dco.uscg.mil/Portals/9/CG-5R/nsarc/LandSweepWidthDemoReportFinal.pdf
- Number 2 has the shape of the ISO 20380 alarm set off time, the i-LIDS ten-second window and the lifeguard 10/20 standard. The 10-second line is borrowed from those two sources and should be changed if the drone's speed leaves people in frame for less. **[read]** https://cdn.standards.iteh.ai/samples/67857/66a010c70cd940dc963def72fa5773eb/ISO-20380-2017.pdf https://assets.publishing.service.gov.uk/media/5a7ac14d40f0b66eab99c6c0/ilids-user-guide.pdf https://s3.amazonaws.com/moreyspiers.com/iltp-5th_edition.pdf
- Number 3 is the false alarm rate that ISO 20380 and the man-overboard rules state per day, restated per flight hour. IAMSAR already prices the cost in flight time by reserving 15% of on-scene endurance for investigating sightings. **[read]** https://cdn.standards.iteh.ai/samples/67857/66a010c70cd940dc963def72fa5773eb/ISO-20380-2017.pdf https://rulesexplorer-docs.bureauveritas.com/documents/nr467/jan2026/467-NR_PartF_2026-01.pdf https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf
- Number 4 answers whether a find was a single lucky frame. Marine radar counts a target as detected at 8 of 10 scans, and i-LIDS fails a track when contact is lost for more than four seconds. **[read]** https://wwwcdn.imo.org/localresources/en/KnowledgeCentre/IndexofIMOResolutions/MSCResolutions/MSC.192%2879%29.pdf https://assets.publishing.service.gov.uk/media/5a7ac14d40f0b66eab99c6c0/ilids-user-guide.pdf

Why a machine-learning judge would accept them:

- Number 1 is recall with the ground-truth track as the unit. It is the limiting case of the mostly-lost measure with the threshold moved from 20% of frames to zero matched frames. **[inference]** from https://arxiv.org/abs/1603.00831
- Number 2 is track latency as defined for radar trackers. **[read]** https://www.academia.edu/64572036/Performance_measures_for_multiple_target_tracking_problems
- Number 3 is NIST's RateFA with hours in place of minutes, and the five-second merge is the i-LIDS rule. **[read]** https://actev.nist.gov/pub/Draft_ActEV_2018_EvaluationPlan.pdf https://assets.publishing.service.gov.uk/media/5a7ac14d40f0b66eab99c6c0/ilids-user-guide.pdf
- Number 4 is HOTA's detection recall computed per track, with the MOT16 80% line for mostly tracked. **[read]** https://arxiv.org/abs/2009.07736 https://arxiv.org/abs/1603.00831
- All four change with the confidence threshold. A threshold sweep gives a curve of people missed against false dispatches per hour, and NIST's convention is to quote the miss rate at one false alarm rate chosen in advance. **[read]** https://actev.nist.gov/pub/Draft_ActEV_2018_EvaluationPlan.pdf

Choices I made without a source and that the team should confirm:

- "At least one mark" is the lenient form of number 1. A stricter form asks for two matched seconds within any ten. The lenient form matches the detection experiment rule, and number 4 exposes single-frame finds.
- The five-second merge in number 3 will join two different false objects that appear in the same seconds. Without system track identities or frame-to-frame registration I see no cleaner rule.
- The 10-second line in number 2 is a convention borrowed from pool and video-alarm practice. No maritime source sets a figure.

## Not verified

- IAMSAR text was read from a third-party copy of ICAO Doc 9731 Volume II. I did not identify its edition or compare it with the current IMO edition. https://www.pc5e.nl/downloads/marcom_other/Doc.9731-EN%20IAMSAR%20Manual%20-%20International%20Aeronautical%20and%20Maritime%20Search%20and%20Rescue%20Manual%20Volume%20II%20-%20Mission%20Co-ordination.pdf
- Coast Guard wording comes from COMDTINST 16130.2H. A bulletin dated 30 October 2026 lists 16130.2I as cancelled and replaced by four volumes (COMDTINST 16101.1, 16101.12, 16101.13 and 16101.14). I did not read those volumes, so current wording may differ. **[read]** https://content.govdelivery.com/accounts/USDHSCG/bulletins/43113bd
- ISO 21195:2020 numeric thresholds. The preview shows the clause titles only. A vendor states 95% detection and at most one false alarm per day on average. **[search summary]** https://marss.com/about/news/marss-mobtronic-man-overboard-technology-achieves-phase-2-iso21195-certification/
- The SeaDronesSee paper's appendix that describes each tracking measure, and the SeaDronesSee challenge page, which timed out.
- HERIDAL figures come from the abstract. The paper's own evaluation section was not read.
- The origin paper for mostly tracked and mostly lost, which MOT16 cites as its reference 30.
- Gorji et al. 2011 was read on academia.edu with broken formatting. The definitions above are paraphrased.
- Koopman's original papers (Operations Research, 1956 and 1957) are paywalled. Sweep width and random search formulas were taken from Frost's Coast Guard text instead.
- Per-victim results in Doherty and Rudol 2007, Niedzielski et al. 2018 and Goodrich et al. 2008.

