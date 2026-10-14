# Example: gearbox reassembly (IMPACT dataset)

**Licence of this folder: CC BY-NC-SA 4.0 — not MIT.** Everything here is derived from the IMPACT dataset:
- the video (re-encoded to 480p, audio removed),
- the frames,
- the human labels (`verdad.json`),
- the chart computed from them.

It may be used only for non-commercial purposes, and adaptations must keep the same licence. See
`LICENSE-DATA-IMPACT` (a summary of the dataset's licence notice; the original is
https://github.com/Kratos-Wen/IMPACT/blob/main/LICENSE-DATA) and https://creativecommons.org/licenses/by-nc-sa/4.0/.

**Attribution:** *IMPACT: A Dataset for Multi-Granularity Human Procedural Action Understanding in Industrial Assembly*,
version 1.1, https://kratos-wen.github.io/IMPACT/ (Hugging Face: `KratosWen/IMPACT`). Trial `LE07UF17_Reassembly_A_004`,
top view.

**Changes made:**
- The video was re-encoded.
- The frame-level hand labels (TAS-B) were mapped to ILO bimanual codes per second, with a fixed rule written before
  measuring (`agent/` in the lab notes).
- Gilbreth's chart was computed on top of the labels.

**How the example was made:**
1. An engineer's review of the first 60 s is simulated with the dataset's human labels.
2. Gilbreth codes the rest of the video.
3. The result is compared with the human labels from second 60 on.

The operator belongs to the test group: the motion prior never saw this person.
