# Continuous labelled footage of people in open water, outside SeaDronesSee

Research date: 2026-11-24. This version replaces the first draft and contains only claims I can trace to a record I read in this session.

Tags used:

- **[read]** I read the primary record myself (a registry or repository API response, the dataset's own page, or a file already on disk). The URL follows the tag.
- **[unverified]** Not confirmed against a primary source in this pass.

Two general web searches were also run. Their result text could not be re-read afterwards, so nothing in this file relies on them. Only metadata was downloaded. No dataset files were fetched.

## Answer

1. Nothing new matches MOBDrone. I found no second downloadable set with consecutive frames, per-frame person boxes and track identities that sits outside the detector's training domain.
2. MOBDrone is confirmed from its Zenodo record and the annotation file on disk. It is CC BY 4.0, with 66 clips, 126,170 frames at 30 FPS and COCO labels carrying a `track_id`. Clips run 1.9 to 235.5 seconds (median 53.7). Each clip has 1 to 17 track IDs, the ID numbers are reused across clips, and 1,332 of 113,408 person boxes have no ID. Key every track by clip name plus `track_id`.
3. SeaDronesSee's multi-object-tracking track is an in-domain control only. Its README gives 22 clips, 54,105 frames and CC0 data, and its sample metadata carries Lake Constance GPS coordinates. Test labels are withheld. Download size, frame rate and whether the released train and validation labels carry track identities are unverified, because the download page could not be reached.
4. AFO and SAR-HumanDetection-FinlandProper stay out. AFO publishes 3,641 still images from 50 videos (4.70 GB, CC BY-NC-SA 3.0) and no source videos. FinlandProper is one 174.2 GB zip (CC BY 4.0, over 72,000 images) and its record mentions no track identities.
5. Shortlist for this week:
   1. MOBDrone, keyed by clip plus `track_id`.
   2. SeaDronesSee tracking, as the in-domain control.
   3. Zenodo record 6526299, raw drone video of a seaside rescue exercise in Cyprus (CC BY 4.0, seven MP4 files of 1.66 to 3.76 GB, no labels). People would have to be labelled by hand.

## Candidates

### MOBDrone

- What it shows: people in the sea simulating a man-overboard rescue, filmed by one drone at 10 to 60 m above mean sea level. 126,170 frames from 66 clips, more than 180K boxes over five classes (person, boat, lifebuoy, surfboard, wood), more than 113K of them person. [read] https://zenodo.org/api/records/5996890
- Licence: CC BY 4.0 (`cc-by-4.0` in the record metadata). [read] https://zenodo.org/api/records/5996890
- Size: 248.57 GB for the whole record. `MOBDrone_videos.zip` is 5.46 GB, `images.zip` is 242.96 GB, the three COCO annotation files are 45.3 MB, 54.6 MB and 60.5 MB, and there is a `README.pdf`. [read] https://zenodo.org/api/records/5996890
- Partial download: every file in the record has its own URL of the form `https://zenodo.org/api/records/5996890/files/<filename>/content`. The 66 videos sit inside one zip, so a single video cannot be fetched alone through this pattern. [read] https://zenodo.org/api/records/5996890
- Frame rate and length: frames were extracted at 30 FPS. [read] https://zenodo.org/api/records/5996890. Grouping the image entries in the annotation file by clip name gives 66 clips of 58 to 7,065 frames, median 1,612. At 30 FPS that is 1.9 to 235.5 seconds, median 53.7. [read] local file `data/mobdrone/annotations_person_coco_classes.json`
- Label format: MS COCO JSON. The person-only file has 126,170 image entries and 113,408 person annotations. The first and last image entries are 1920 x 1012. [read] local file `data/mobdrone/annotations_person_coco_classes.json`
- Track identity: each annotation has `attributes` with `occluded`, and most also have `track_id` and `keyframe`. 1,332 of the 113,408 person annotations have no `track_id`. All 66 clips have person tracks. [read] local file `data/mobdrone/annotations_person_coco_classes.json`
- Track ID scope: unique IDs per clip range from 1 to 17. Twenty clips have 4, fifteen have 2, eight have 6, six have 3, four have 1, four have 5, three have 7, three have 10, and one each has 8, 9 and 17. The largest ID value anywhere is 23, and ID 0 appears in clips from both recording days, so the numbers are reused across clips. [read] local file `data/mobdrone/annotations_person_coco_classes.json`. Whether the numbering restarts per clip or per source recording was not determined. [unverified]
- Splits: the record calls the set a test benchmark and offers a split by filename prefix. `DJI_0804` is the test set with 37,604 images and `DJI_0915` is the training set with 88,568 images. [read] https://zenodo.org/api/records/5996890
- Paper: the record links https://arxiv.org/abs/2203.07973. I did not read the paper, so nothing here is drawn from it. [unverified]

### SeaDronesSee multi-object tracking (in-domain control only)

- What it shows: the benchmark the detector was trained on. The README lists a multi-object-tracking set of 22 video clips with 54,105 frames, and a single-object-tracking set of 58 training, 70 validation and 80 testing clips whose frames are taken from the multi-object-tracking download. [read] https://raw.githubusercontent.com/Ben93kie/SeaDronesSee/main/README.md
- Licence: "Code is MIT license, dataset is Creative Commons CC0 1.0 Universal". [read] https://raw.githubusercontent.com/Ben93kie/SeaDronesSee/main/README.md
- Label format: frames are PNG files with JSON annotation files. The README names `instances_test_objects_in_water.json` and `instances_test_swimmer.json`. Its sample image entry is 3840 x 2160 and carries the source video name, `video_id`, `frame_index`, a timestamp, GPS position (47.671949 N, 9.269724 E), altitude, gimbal pitch and speed. [read] https://raw.githubusercontent.com/Ben93kie/SeaDronesSee/main/README.md
- Track identity: the README describes the submission format as one line per object per frame, `[frame_id],[object_id],x,y,w,h`, with the object ID assigned by the submitter's tracker. [read] same URL. It does not show a ground-truth annotation, so whether the released train and validation labels carry a track identity per person is not confirmed. [unverified]
- Labels available: test-set labels are withheld for object detection, single-object tracking and multi-object tracking. Only inputs are handed out and scoring runs on the project's server. [read] same URL
- Total size, single-sequence download, frame rate and sequence length: the download page https://seadronessee.cs.uni-tuebingen.de/dataset did not respond over https or http. [unverified]
- The first draft also gave a 21 / 17 / 19 clip split, said the challenge merges boats, swimmers and floaters into one class, and said no official frame rate is stated. I cannot trace those to a source. [unverified]
- Difference from MOBDrone: lake water at Lake Constance and the detector's own training domain, so results on it say nothing about unseen footage.

### AFO (Aerial dataset of Floating Objects)

- What it shows: 3,641 images extracted from 50 drone videos, with 39,991 annotated objects in six classes (human, wind/sup-board, boat, buoy, sailboat, kayak). The paper reports 3,647 images and the Kaggle page says six were never released. [read] https://www.kaggle.com/api/v1/datasets/view/jangsienicajzkowy/afo-aerial-dataset-of-floating-objects
- People: 33,174 of the objects are `human`. [read] https://huggingface.co/datasets/jgasienica/afo-dataset/raw/main/README.md
- Licence: CC BY-NC-SA 3.0, non-commercial. [read] local file `data/afo/readme.txt`. Kaggle lists it as "Attribution-NonCommercial-ShareAlike 3.0 IGO". [read] Kaggle URL above
- Size: 4,696,173,055 bytes (4.70 GB) on Kaggle. [read] Kaggle URL above
- Source videos: the Kaggle description and the Hugging Face card describe images only, in three parts of 1,014, 1,222 and 1,405 JPEG files. The Hugging Face repository states it reproduces the Kaggle release byte for byte. Neither offers the 50 videos. [read] both URLs above
- Label format: Darknet YOLO text files, one object per line as `class cx cy w h`, normalised to the image size. [read] local file `data/afo/readme.txt` and the Hugging Face card
- Track identity: none. The label format has no identity field. [read] Hugging Face card
- Filenames: images are named with a clip prefix and a number, for example `a_102.jpg` and `i3_200.jpg`. Of the 17 filename prefixes in the test list, 14 appear nowhere else. [read] Hugging Face card. Whether the numbers are consecutive frames close enough in time to rebuild short runs was not checked. [unverified]
- Single-file download: not tested. [unverified]
- Difference from MOBDrone: many source clips from various drone cameras and four image resolutions, with swimmers, boards and kayaks, against MOBDrone's one drone and staged man-overboard scenes.

### SAR-HumanDetection-FinlandProper

- What it shows: "a dataset for human detection from an image, recorded with a drone flying above water area, where the target is swimming/floating", recorded in Finland Proper at three locations between 2020-06-01 and 2020-09-15. Over 72,000 images at 1920 x 1024. [read] https://metax.fairdata.fi/v3/datasets/f3f13aa2-88ff-4c76-ab75-1ff8cd28f3d1
- Licence: CC BY 4.0, open access. [read] same URL
- Size and partial download: one file, `SAR-HumanDetection-FinlandProper.zip`, of 174,248,729,667 bytes (174.2 GB). The registry lists no other file. The first draft's figure of about 162 GB was wrong. [read] https://metax.fairdata.fi/v3/datasets/f3f13aa2-88ff-4c76-ab75-1ff8cd28f3d1/files
- Label format: "xyrb-format" per the record. [read] first Metax URL above
- Track identity and sequences: the record does not mention video sequences, frame rate or track identities. [unverified]
- Paper: the record relates the set to "On automatic person-in-water detection for marine search and rescue operations" (IEEE Access). I did not read it. [unverified]
- Sibling Tampere sets: Metax searches for "SAR-HumanDetection" and "person-in-water" return only this record. A search for the first author's surname returns one more, Tampere-WaterSeg (158,980,075 bytes, issued 2019-10-16). [read] https://metax.fairdata.fi/v3/datasets?search=Taipalmaa&limit=20. I did not read the Tampere-WaterSeg record, so its content is unverified. [unverified]
- Difference from MOBDrone: Finnish waters at three locations, against MOBDrone's sea footage from one drone.

### Zenodo 6526299, "Drones' footage of a search-and-rescue exercise scenario (at seaside)"

- What it shows: raw MP4 video captured by drones during a search-and-rescue exercise on 13 February 2022 at the seaside of Agios Georgios Pegeias in Cyprus. The exercise was run by the Cyprus Civil Defence and filmed by the KIOS centre at the University of Cyprus for the ARTION project. [read] https://zenodo.org/api/records/6526299
- Licence: CC BY 4.0, open. [read] same URL
- Size: 20.79 GB in seven files. `DJI_0786.MP4`, `DJI_0787.MP4`, `DJI_0788.MP4` and `DJI_0790.MP4` are about 3.76 GB each. `DJI_0789.MP4` is 1.66 GB, `DJI_0791.MP4` is 1.93 GB and `DJI_0792.MP4` is 2.17 GB. [read] same URL
- Partial download: each file is listed separately. The pattern `https://zenodo.org/api/records/6526299/files/DJI_0789.MP4/content` follows the file links in the MOBDrone record and was not test-downloaded. [unverified]
- Labels and track identity: none. The record describes raw video files only. [read] same URL
- Frame rate, clip length and whether people appear in the water: not stated in the record. [unverified]
- Difference from MOBDrone: a civil-defence exercise at a Cyprus shoreline in winter, without labels.

### MAMMS (Zenodo 17979190)

- What it shows: a multimodal set from ground sensors, low-altitude drones (colour and thermal) and satellite, covering coastal and maritime scenarios with people, vessels, vehicles and simulated oil spills. Published 2025-12-22. [read] https://zenodo.org/api/records/17979190
- Access: restricted. The record lists no licence and no files. A user agreement must be registered before a download link is sent. [read] same URL
- Label format: one `annotations.xml` per scenario and sensor, with a box per object (`label`, `xtl`, `ytl`, `xbr`, `ybr`) and an attribute holding the track ID. Frames are image files. [read] same URL
- Track identity: the record says each box has a track ID kept for the full sequence, across occlusions. Its tables give track counts for the thermal drone sequences (for example scenario bg7 with 808 images, 8,801 person boxes and 44 tracks) and show a dash in the track column for every colour drone sequence. [read] same URL
- Size, frame rate and whether the people are in the water: not stated in the part of the record I read. [unverified]
- Practicality: the agreement step makes it unlikely to be usable this week.

### Seagull

- What it shows: multi-camera, multi-spectrum image sequences from a fixed-wing drone flying over the sea, boats, life rafts and other floating objects, in visible, near-infrared, infrared and hyperspectral bands. [read] https://vislab.isr.tecnico.ulisboa.pt/seagull-dataset/
- Access: "available upon request". [read] same URL
- People, licence, label format, size and frame rate: the page mentions none of these. [unverified]

### Other Zenodo records opened

- 24106105, UMD (Unified Maritime Dataset): a collection of existing ship, boat and buoy sets for surface-vehicle obstacle detection, in three zips of 23.79, 9.82 and 1.56 GB, CC BY 4.0. The sources named in the part of the description I read are vessel sets. [read] https://zenodo.org/api/records/24106105
- 7755621, Aerial Water Buoys Dataset: top-view images of buoys off Larnaca and Protaras in Cyprus, used in place of people. One class, `buoy`. Ten zips by altitude, 42.5 GB, CC BY 4.0. No people. [read] https://zenodo.org/api/records/7755621
- 7740081, Small Object Aerial Person Detection Dataset: 3,136 frames from flights over the University of Cyprus campus and Civil Defense exercises, in YOLO, COCO and VOC formats, 3.72 GB, CC BY 4.0. The record does not mention water or track identities. [read] https://zenodo.org/api/records/7740081

## Sweeps

### Zenodo

- A dataset search for `"man overboard"` returns one record, MOBDrone. [read] https://zenodo.org/api/records?size=25&type=dataset&q=%22man%20overboard%22
- A search for `SAR-HumanDetection-FinlandProper` returns nothing relevant in the first 25 results, consistent with that set living on Fairdata. [read] https://zenodo.org/api/records?size=25&type=dataset&q=SAR-HumanDetection-FinlandProper
- Six broader searches (maritime search and rescue drone video, swimmers, people in water, thermal sea rescue, drowning, maritime tracking) produced the records described above and no other on-target title in the first 25 results each.
- One listed record was not opened: 6370315, "Dataset of UAV thermal video sequences with annotations for MOTS benchmarking" (1.74 GB, CC BY 4.0). Its content is unverified. [unverified]
- Four follow-up searches were refused with HTTP 403 ("unusual traffic"), so the Zenodo sweep is incomplete.

### Hugging Face

Dataset searches through `https://huggingface.co/api/datasets?search=<term>` for seadrones, maritime, swimmer, rescue, mobdrone, overboard, drowning and afo. [read]

- SeaDronesSee mirrors, for example `dronefreak/SeaDronesSee`, tagged CC0 and object detection. These are the detector's own domain.
- AFO mirrors: `jgasienica/afo-dataset`, `Voxel51/AFO-Aerial_Floating_Objects` and `12edf/AFO-Aerial_Floating_Objects`.
- `AhsanBB/Maritime_Visual_Tracking_Dataset_MVTD`: 182 single-object-tracking sequences, 150,058 frames at 30 and 60 FPS, CC0. Its four categories are boat, ship, sailboat and unmanned surface vehicle. No people. [read] https://huggingface.co/datasets/AhsanBB/Maritime_Visual_Tracking_Dataset_MVTD/raw/main/README.md
- `madokalif/rescuebench-drone-search-v1`: simulator demonstrations over land maps. [read] https://huggingface.co/datasets/madokalif/rescuebench-drone-search-v1/raw/main/README.md
- `Maritime-dataset/UAV_Dataset`: an empty repository with zero bytes stored. [read] https://huggingface.co/api/datasets/Maritime-dataset/UAV_Dataset
- No other result for these terms was aerial footage of people in water.

### arXiv

Two API queries returned these titles. I read titles only, so whether any has a public dataset is unverified. [unverified]

- https://arxiv.org/abs/2604.18088, "Autonomous Unmanned Aircraft Systems for Enhanced Search and Rescue of Drowning Swimmers" (2026-04-20)
- https://arxiv.org/abs/2511.19728, "Maritime Small Object Detection from UAVs using Deep Learning with Altitude-Aware Dynamic Tiling" (2025-11-24)
- https://arxiv.org/abs/2608.15830, "MITE-Net: SWaP-Optimized 4K Video Tiny Target Perception for Embodied Edge SAR" (2026-08-16)

## Not checked

- WaterScenes. The repository https://github.com/WaterScenes/WaterScenes exists and GitHub detects no licence for it. I did not read its readme or data pages. [unverified]
- NOMAD. I did not read its paper or find its data page. [unverified]
- The MOBDrone paper and the AFO paper. [unverified]
- The SeaDronesSee download page and the MaCVi dataset page, including size, frame rate and per-sequence download. [unverified]
- Kaggle beyond the AFO page. [unverified]
- A wider Zenodo sweep, cut short by the 403 responses. [unverified]
- The Tampere-WaterSeg record and Zenodo record 6370315. [unverified]

## Shortlist for this week

1. **MOBDrone, already on disk.** It is the only set confirmed to have consecutive frames, person boxes and track IDs outside the detector's domain. Key tracks by clip name plus `track_id`, and decide how to treat the 1,332 person boxes without an ID.
2. **SeaDronesSee multi-object tracking, as an in-domain control.** It shows how the vote behaves on footage the detector knows. Before fetching, confirm the download size and that the train or validation labels carry track identities, since test labels are withheld.
3. **Zenodo 6526299, with hand labelling.** One file of 1.66 GB is the smallest practical download. It has no labels, so it serves as unseen footage for manual spot checks of the vote, after confirming that people are visible in the water.

AFO, SAR-HumanDetection-FinlandProper, MAMMS and Seagull stay off the list for the reasons given in their sections.

