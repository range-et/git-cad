# DualBrep CUDA reconstruction investigation — 2026-11-09

This is external-backend evidence, not a CAD-GIT execution feature. The published
CAD-GIT checkout on C110P was `97b81437a5142bcb9dba4cdee71a97eb93bab12c`;
it does not contain the Mac working tree's job-preparation integration.
Open follow-ups are [issues #1–#4](../issues.md).

## Environment and provenance

- C110P, Windows 11 Pro 10.0.26300, RTX 5070 Ti (16,303 MiB), driver 621.14.
- Separate environment: `C:/Users/range/Desktop/dualbrep-cuda-check/occ-env`.
- Python 3.12.16; Torch 2.7.1+cu128; torchvision 0.22.1+cu128;
  torch_cluster 1.6.3+pt27cu128; pythonocc-core 8.0.1.1.
- DualBrep fork/upstream code: `9707b4b4e531943f38e83092ff7ad833cc60b2cb`.
  No upstream source patches in the initial smoke runs.
- Official point-cloud VAE and parametrizer checkpoints downloaded separately;
  hashes and exact environment packages retained in the remote report directory.
  Model weights are not part of CAD-GIT or this report.
- CUDA availability, synchronized matrix multiplication compared with CPU, CUDA
  farthest-point sampling and fresh-process OpenCASCADE box STEP round-trip passed.

Remote evidence was read through the connected C110P chat on November 9, after
reconnecting. Paths below refer to that machine, not the development Mac.

## Initial two samples

Both used `config_pc.yaml`, resolution 256, one sample, rebuild rotation 3,
default 200-step latent optimization, and serial postprocessing. Contrary to an
earlier investigation assumption, the checked-in config defaults to **256**, not
512; the full pipeline normally tries **all 24 rotations**. These were bounded
single-candidate smoke tests, not the complete upstream benchmark.

| Sample | AE / parametrizer | STEP re-import | Interpretation |
| --- | --- | --- | --- |
| `00013293` | Completed; 53 reconstructed faces, 295 edges | General shape-valid check passed; 53 faces, six shells, zero solids | Failed closed-solid reconstruction; intermediate STEP is not an accepted solid |
| `00030157` | Completed; 25 reconstructed faces, 122 edges | Valid shape; one solid, one shell, 25 faces; positive volume 0.5585021468322583 | Successful solid reconstruction for this sample/candidate; fidelity and physical scale still unqualified |

Successful output:
`C:/Users/range/Desktop/dualbrep-cuda-check/brep_second/00030157.step`
(1,095,155 bytes), SHA-256
`079ba4cf80139d4b45f0354ef261ed45503f992e4c3508bb404f1f9b7ee1c6fe`.
Re-imported dimensions: approximately `1.812869 × 0.712394 × 1.814040` in
**upstream normalized coordinates**, not restored manufacturing units.

Evidence directory: `C:/Users/range/Desktop/dualbrep-cuda-check/`:
`REPORT.txt`, `commands.ps1`, `pip-freeze.txt`, `conda-explicit.txt`,
`step_validation_second.json`, reconstruction/rebuild/postprocessing logs and
preserved intermediate artifacts. General BRepCheck validity is insufficient:
it can accept a compound of valid open shells. A subprocess exit code is also
insufficient, because upstream may finish while individual shapes fail.

## Windows setup findings

The pinned libigl dependency had no matching wheel in this tested setup and no
local C++ compiler. It was omitted only for the default point-cloud path, which
does not use it. Implicit preprocessing/alternative clustering are not qualified.

Importing Lightning before OpenCASCADE STEP support reproduced a DLL-load failure;
Torch or Open3D before STEP support did not reproduce it in the tested probes.
Fresh stage processes worked. This establishes an import-order compatibility
problem in this environment, not its underlying DLL root cause. Keep stages
isolated in the future service and retain a fresh-process compatibility probe.

## Investigation and acceptance

The second sample rules out a universal CUDA/STEP execution failure. It does not
identify why the first shape failed. Compare other candidates using the same AE
output, inspect failed trimming/free boundaries/sewing, then vary resolution only
if justified. Preserve each experiment in a distinct output directory and retain
failed candidates. Do not raise tolerance solely to turn the success flag green.

Upstream postprocessing can use large normalized sewing tolerances and patch
holes. Its `_save_gap_and_vertices` measures gap after resetting/recomputing
stored tolerances; retain that evidence alongside closure and solid checks.
A useful CAD-GIT result must additionally restore source units and placement,
measure geometric deviation, and report repairs or discarded geometry.

## Candidate comparison on the failed shape

Using the same resolution-256 AE output, rotations **0 and 7 both sealed**. No
higher-resolution AE rerun or tolerance increase was needed. Independent STEP
checks found one closed, valid positive-volume solid, one shell, 53 faces and zero
free boundary edges for each. Volumes were approximately 0.410656 (rotation 0)
and 0.415894 (rotation 7), in normalized units cubed.

A diagnostic replay of rotation 3 found **faces 49 and 50 could not be trimmed**.
The subsequent sewing attempts failed across upstream's existing tolerance sweep,
and its hole-filling fallback failed too. The reported 53-face intermediate STEP
must not be mistaken for 53 successfully trimmed/sewn faces.

This establishes a candidate-dependent trimming/sewing failure. It does not yet
identify the exact numerical/geometric reason those two face trims fail, or prove
that platform differences have no effect. The bounded investigation does not
need a resolution-512 experiment to establish that this shape can seal at 256.

Production implication: do not hard-code a single orientation as a reliable
converter. Use a bounded candidate search (upstream uses all 24), retain each
outcome, and independently validate selected output. Continue measuring source
fidelity and repair/tolerance requirements; closure alone is not acceptance.


## Final bounded findings

The failed candidate predicted 149 unique undirected face relationships; both
successful candidates predicted 153. Both added `8–49`, `13–16`, `28–32` and
`49–50`, retaining all original pairs. No run reported pruning predicted edges.
Missing relationships involving the failing faces are consistent with the trim
failure; causality was not isolated by manually repairing topology.

The replay retained 51/53 trimmed faces. Even at the existing maximum sewing
tolerance of 0.08, the no-optimization attempt had 15 free edges and the optimized
attempt had 10. Hole filling raised `Standard_NoSuchObject`. The fallback replaced
failed trims with untrimmed faces: its 53-face STEP contained six open shells,
39 free boundary edges and zero solids. Successful alternatives required neither
hole patches nor postprocessing geometry optimization. A repeated rotation-0
trace sealed at upstream's existing 0.015 tolerance. No tolerance overrides,
core-source patches, training, or new AE reconstruction were performed.

| Candidate | Recomputed edge gap | Input-point → tessellated-surface mean | p95 | Observed maximum |
| --- | --- | --- | --- | --- |
| Failed rotation 3 | Not applicable | 0.004201 | 0.010323 | 0.062202 |
| Rotation 0 | 0.0105314 | 0.001810 | 0.004967 | 0.007850 |
| Rotation 7 | 0.0135863 | 0.001409 | 0.003870 | 0.009473 |

All values are **normalized units**. The input-distance comparison used all 8,192
input point-cloud vertices and nearest triangles of the tessellated STEP
(deflection 0.002, angle 0.2). Additional surface comparisons used 20,000
area-weighted samples per mesh. These are finite, tessellated approximations,
not exact B-spline/ground-truth CAD surface distances or continuous Hausdorff error.
Recomputed edge gaps are about 0.59% and 0.75% of the normalized input max span
1.8; solid validity does not qualify precision CAD use.

A coarse `BRepBndLib.Add` bound overstated rotation 0's Z extent. Tighter
`AddOptimal` bounds without shape tolerances and tessellation gave dimensions
`1.800301 × 0.599457 × 1.021176`, compared with the AE mesh's
`1.800025 × 0.600232 × 1.019991`. Do not interpret the earlier coarse bound
as evidence of large deformation. Rotation 7 had lower sampled mean/p95 errors;
rotation 0 had lower observed maximum and recomputed gap. No universal best
candidate is established; upstream promoted rotation 0.

Rotation also changes deterministic sampling (`1000*k + 7`), so orientation and
resampling effects are confounded. Same-environment successes argue against a
blanket Windows/OCC failure, but no cross-platform same-candidate comparison was
performed. The exact trim failure mechanism remains an investigation topic.

Final evidence on C110P:
`C:/Users/range/Desktop/dualbrep-cuda-check/investigation/INVESTIGATION.txt`,
`RESULTS.json`, `commands.ps1`, `original_trace_summary.json`,
`topology_*.json`, `connectivity_comparison.json`, `geometry_comparison.json`.
The accepted diagnostic output is `investigation/rotations/00013293.step`.
Original failed artifacts and hashes were preserved; both upstream checkouts
remained clean. Investigation ended after the two alternative rotations.
