CAD-GIT / DualBrep prepared inputs

STATUS: PREPARED ONLY. No inference has run and this bundle contains no STEP.
Keep this committed bundle immutable. Copy inputs into a separate runtime work
directory when the inference adapter is implemented and validated.

request.json pins the source version, parts, material associations, backend
revision and parameters. Each inputs/partNNNN.ply is one connected component in
world meters, Z up. Parts must be reconstructed separately: upstream segmentation
can discard all but the largest connected component. Explicit shell splitting
may change the interpretation of cavities or nested bodies.

An external environment needs the pinned DualBrep code, its dependencies and the
pc_vae / parametrizer checkpoints. The published environment uses CUDA. Do not
install its Torch/OCC dependencies into CAD-GIT's environment. runtime.example.json
is a template, not an active service configuration. No models are downloaded here.

Future adapter stages: point-cloud autoencoder (not generative diffusion), face
segmentation, parametrizer and STEP rebuilding. Never rely only on exit code:
upstream can skip shapes and return success. Check every expected part output.

CRITICAL: default upstream normalization returns coordinates in a normalized box.
For each part restore world meters with point * scale_m + center_m from its
normalization record, then multiply by 1000 and explicitly write STEP millimeters.
Re-read the STEP and compare dimensions and placement. Do not import normalized
output as if it were correctly sized CAD. Do not enable per_axis_norm or change
upstream normalization without updating and validating this contract.

Require OCC parsing/solid checks, missing-part checks, physical-unit deviation,
and user review before accepting reconstructed output. A valid solid can still
differ from the original. Generated NURBS/topology do not recover original control
points, feature history, face identities or shaders. Materials remain associated
with source parts; new face correspondence is not established.

The code repository is Apache-2.0. Checkpoint distribution terms must be checked
separately; this bundle includes no third-party code or weights.
