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

The dataset authors do not endorse this project.
