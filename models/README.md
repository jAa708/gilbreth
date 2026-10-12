# models/

- `hand_landmarker.task` — MediaPipe hand model (Apache-2.0). Downloaded automatically on first use.
- `motion_prior_impact.npz` — **motion prior**: per-hand, per-second motion features with activity labels from
  9 operators of the IMPACT dataset. It is a derivative of IMPACT, licensed **CC BY-NC-SA 4.0**, so it is **not part
  of this MIT repository**. It is published separately under that licence with attribution; set
  `GILBRETH_PRIOR_URL` (or drop the file here) to use it. Without it, the agent runs in *MIT-pure* mode (calibration
  learns only from the seconds you reviewed), which measured clearly lower — see `docs/RESULTS.md`.
