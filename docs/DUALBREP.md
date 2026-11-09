# Optional B-rep reconstruction: prepared jobs and device portability

Status, November 9, 2026: **job preparation implemented; inference and STEP output
pending a separately configured and validated runtime**. The user selected this
first step because the development machine is Apple Silicon. Nothing downloads
models, changes original USD history, or converts an ordinary Rhino handoff.

A separate upstream CUDA smoke run on C110P has since produced one independently
validated solid and one failed shell-only result. See the
[dated investigation](DUALBREP_CUDA_INVESTIGATION.md) and [open work](../issues.md).
This does not activate Git CAD execution or qualify Apple Silicon.

## Product boundary: optional external service

Decision, 2026-11-09: reconstruction is outside Git CAD's core scope. The existing
[range-et/DualBrep fork](https://github.com/range-et/DualBrep) is the intended home
for a future independently versioned Docker service. No service image or Docker
integration is implemented or qualified yet. Further model/backend development
belongs there, and is not a Git CAD release requirement.

Git CAD's future adapter should only:

1. Probe Docker, the configured provider and its protocol/device capabilities.
2. Submit an immutable prepared job on explicit user request, with bounded
   resources, cancellation, timeout and visible progress/logs.
3. Read a versioned result manifest containing per-part outcomes, source/job IDs,
   provider/model versions, units, artifact hashes and geometry-validation results.
4. Verify returned artifacts and record accepted results as new derived history;
   preserve the original job, USD snapshots and main selection.
5. If Docker, the image, a compatible device or a successful result is unavailable,
   explain the specific reason and leave the rest of Git CAD fully usable. Do not
   silently change execution targets, install runtimes, or retry indefinitely.

The provider owns inference, candidate search, fitting, sewing, unit restoration,
geometry-quality diagnostics and its dependency stack. Git CAD owns job/result
bookkeeping and honest acceptance of the provider's declared results. Git CAD does
not promise that every mesh becomes a solid or that reconstruction restores
original native feature history.

The job/result protocol should be platform-independent. Container architecture
and accelerator support remain explicit provider capabilities, qualified per
host/runtime; a multi-architecture image is not proof of GPU portability. Apple
Silicon acceleration is deferred provider research, not a prerequisite for shipping
Git CAD. An unsupported local platform may simply report reconstruction unavailable.
The native Windows CUDA experiments are not Docker validation.

## Using the preparation feature

Open a saved version and choose **Prepare B-rep job…** beside Export STL. Selected
prim/subtree paths are frozen when the dialog opens; no selection means the whole
saved scene. The draft must be saved first. The job contains separate PLY inputs,
units, transforms, exact source identity and material associations. It does not
contain a STEP or pretend that original NURBS/feature history has been recovered.

```sh
git-cad -p /path/to/project brep prepare ASSEMBLY_ID
git-cad -p /path/to/project brep prepare SNAPSHOT_ID --select /World/Part
git-cad -p /path/to/project brep list
git-cad -p /path/to/project brep show JOB_ID
git-cad -p /path/to/project brep verify JOB_ID
```

Jobs are committed under `artifacts/brep_jobs/<id>/`. Each includes `request.json`,
`inputs/partNNNN.ply`, `runtime.example.json`, `README.txt`, a hash inventory and
commit marker. The runtime example is a template, not an active service. Future
execution must write a distinct derived result artifact; never modify this bundle.

Disconnected meshes are rejected by default. `--split-components` explicitly
creates separate reconstruction inputs. Nested disconnected shells can represent
cavities, so splitting is a modeling decision. Upstream segmentation retains only
the largest connected component: feeding an entire engine at once could discard
parts. No boolean union occurs. Subdivision requires `--allow-base-mesh`; evaluated
subdivision/displacement are not implied.

Inputs retain world-space meters and Z-up in double-precision PLY coordinates.
The request records the actual exported bounding box and upstream's inverse
normalization: `world_m = normalized * scale_m + center_m`. Future STEP output must
apply that transform, convert to explicit millimeters and re-read to verify its
placement and size. The backend's default normalized STEP is not directly suitable
as a correctly sized Rhino model.

## Optional runtime and activation policy

Git CAD does not depend on Torch, CUDA or pythonocc-core. Probe a separate runtime:

```sh
git-cad brep doctor --python /path/to/backend/bin/python --checkout /path/to/DualBrep
```

The UI runtime check also reads `CADGIT_DUALBREP_PYTHON` and
`CADGIT_DUALBREP_CHECKOUT` from its launch environment. The probe runs outside the
GUI process. It checks imports, CUDA availability/basic FPS execution, checkout
revision and expected checkpoint paths. Preparation remains available without it.

Readiness is layered: GPU detected → prerequisites present → provider operations
validated → complete reconstruction and STEP/Rhino qualification. A CUDA GPU alone
is insufficient. `cuda_prerequisites_ready` is a preflight result, not certification
of checkpoint compatibility or geometry quality. `execution_available` remains
false in this preparation-only release, even when prerequisites pass. A future
validated adapter can activate automatically for a compatible configured CUDA
runtime. Unvalidated MPS/CPU environments must not activate conversion.

The inspected upstream revision is
`9707b4b4e531943f38e83092ff7ad833cc60b2cb`. Source code is Apache-2.0. The published
checkpoint archive is approximately 13 GB, and its model endpoint did not declare
license metadata when inspected; check checkpoint terms separately before use or
redistribution. No weights or upstream source are bundled by Git CAD.

## Apple Silicon feasibility

This is a proposed port, not an implemented or tested neural backend. Direct source
inspection identified the following work:

| Upstream constraint | First portable implementation |
| --- | --- |
| CUDA-specific Torch/torchvision/torch_cluster requirements | Separate backend dependency profiles; platform-neutral Torch for macOS. |
| CUDA-or-CPU selection only | Explicit auto/cuda/mps/cpu policy using actual device availability. |
| Unconditional CUDA stream synchronization in rebuild_model | Device-aware synchronization; no-op CPU, MPS sync for Metal. |
| torch_cluster FPS native operator dispatches CPU/CUDA, not MPS | CPU FPS over detached inputs; move the sampled indices back to the neural device. |
| Large CUDA query batches and GPU-process defaults | One neural worker, configurable decoder chunks and measured memory bounds. |
| OCC/geometry postprocessing | Keep on CPU initially. |

Sampling must preserve all six XYZ+normal dimensions, batch offsets, ceil(N×ratio),
and start-point/seed semantics. Ordinary XYZ-only point-cloud downsampling changes
the model's inputs. An independent synthetic NumPy probe selected 4,096 of 32,768
six-dimensional samples in 1.04 seconds on this ARM64 Mac. That supports feasibility
of CPU sampling; it is not model parity or output-quality evidence.

Next qualification steps: CPU FPS parity fixtures; a CPU inference baseline;
MPS probes for attention, trilinear interpolation, 3D pooling, grid_sample/cdist
and their optimization gradients; full point-cloud reconstruction at bounded
resolution; comparison with CUDA; then valid, correctly sized STEP reopened in
Rhino. PyTorch's fallback flag cannot repair a custom native operator or a CUDA
synchronization call. Apple's Metal MPS and NVIDIA's CUDA Multi-Process Service
(also called MPS in upstream scripts) are unrelated.

## Required gates before enabling execution

Validate every expected part output rather than subprocess exit status: upstream
can skip shapes and still finish successfully. Record exact checkpoint hashes,
parameters, code revision, units/inverse transforms, per-part outcomes, gap and
source-to-result deviation in physical units. OpenCASCADE validity alone does not
prove dimensional fidelity; upstream may patch holes. Preserve partial failures
and logs, require review before adopting results, and keep original USD/main intact.

A real CUDA → STEP → Rhino roundtrip and a separate MPS qualification remain
pending. `rhino3dm` cannot directly import STEP; eventual automatic `.3dm` creation
needs a supported native Rhino/OCC handoff. The first validated output should be
a STEP that Rhino can import normally.

Primary sources inspected:

- [DualBrep pipeline](https://github.com/AutodeskAILab/DualBrep)
- [Normalization](https://github.com/AutodeskAILab/DualBrep/blob/9707b4b4e531943f38e83092ff7ad833cc60b2cb/dataset.py)
- [Component filtering](https://github.com/AutodeskAILab/DualBrep/blob/9707b4b4e531943f38e83092ff7ad833cc60b2cb/clustering.py)
- [CUDA synchronization](https://github.com/AutodeskAILab/DualBrep/blob/9707b4b4e531943f38e83092ff7ad833cc60b2cb/rebuild_model.py)
- [FPS dispatch](https://github.com/rusty1s/pytorch_cluster/blob/master/csrc/fps.cpp)
- [PyTorch Metal backend](https://docs.pytorch.org/docs/2.7/notes/mps.html)
- [Published checkpoints](https://huggingface.co/ADSKAILab/DualBrep/tree/main)
