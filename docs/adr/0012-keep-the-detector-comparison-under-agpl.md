# Keep the trained-detector comparison under AGPL-3.0, apart from the MIT code

The free SeaDronesSee detector and the library that runs it are licensed AGPL-3.0, while the rest of the repository is MIT. The comparison script lives in its own folder under AGPL-3.0, and the detector weights are downloaded at run time instead of being committed. The search tool imports nothing from that folder, so anyone can reuse the tool under MIT alone.

November 24: the detector became the first pass of the search itself, in `--mode detector-check`. The search tool runs `detector/run_detector.py` as a separate program with a Python the user names, and reads the `boxes.json` it writes. It still imports nothing from the AGPL folder, so the tool stays reusable under MIT, and only the separate detector program carries the AGPL terms.
