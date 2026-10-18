# Factory examples — source and licence

Folders: `examples/factory_plastic/`, `examples/factory_cardboard/`, `examples/factory_screw/`.

**Source:** *Factory Manipulation Videos* by Procedural Robotics Inc.,
https://huggingface.co/datasets/procedural-robotics/factory-manipulation-videos. Licensed under
**CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/). Workers' faces were blurred by the dataset authors.

| Example | Original file | Excerpt |
|---|---|---|
| Plastic parts assembly | `plastic_assembly_station05_worker032.mp4` | 60–210 s |
| Cardboard handling | `cardboard_manipulation_station04_worker026.mp4` | 60–210 s |
| Screw assembly with a suspended screwdriver | `screw_assembly_station12_worker003.mp4` | 60–210 s |

**Changes made:**
- Each excerpt was cut from the original take and re-encoded (H.264, 480p for the app).
- One frame per chart row was extracted.
- Gilbreth's bimanual chart, method alerts and improvement plan were computed on top of the video.

Each excerpt holds several units, so the app gives its times per 150-s clip, not per unit.

**Sample clip for "Try your own video":** `examples/factory_screw/sample_20s.mp4` is a 20-second excerpt of the
same take, `screw_assembly_station12_worker003.mp4` (107–127 s of the original, that is 47–67 s of the screw
example: two full cycles with both hands in view, the left one holding the part while the right one drives the
screws), cut and re-encoded (H.264, 1280×720). Until 18 Oct it was 80–100 s, mostly a wait between parts. Same source, same CC BY 4.0 licence and attribution. The app offers
it to visitors with no workstation video at hand, and it goes through exactly the same path as an upload.

The dataset authors do not endorse this project.
