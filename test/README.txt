Bridge test workspace — 2026-11-07

source/model.3dm: isolated Rhino fixture, one 20 mm BRep cube in millimeters.
source/scene.blend: BridgeTest scene containing the imported USD cube; the
original Blender default Scene is also retained. Saved as a copy.
usd/scene.usda: portable OpenUSD root, composing look.usda over geometry.usda.
usd/geometry.usda: actual Rhino native USD export; Y-up, millimeter units.
usd/look.usda: reserved empty look layer; no look write-back is implemented.
bridge.json: proposed project config, not an implemented runtime contract.
.bridge/connections.local.json: machine-local connection observations, ignored.
verification.json: fixture checks and initial file hashes.

The active Rhino document was not modified. Blender's BridgeTest scene is active;
its original scene was retained. The fixture GUID is
5d31d8a7-9f40-4c7f-aef0-ff43ee860001. Its actual exported mesh prim is
/Rhino/Geometry/Default/CalibrationCube_20mm_mesh0.
The GUID/prim mapping on the imported object was added explicitly for this
fixture; automatic identity preservation is not implemented or proven.

Proposed future layout:
  history/<revision-id>/
    manifest.json       parent revision, hashes, versions, settings, timestamps
    source/             paired .3dm and .blend saves
    usd/                complete composable layer set
    assets/             dependencies, copied or content-addressed
    bridge.json
  artifacts/<kind>/<artifact-id>/
    manifest.json       source revision, settings, hashes, units, tool version
    ...                 output and any required dependencies

Kinds can grow freely: prints, renders, drawings, animations, simulations, etc.
Do not create empty folders for every possible future output type.
History checkpoints are immutable, mutually consistent project snapshots.
Artifacts are immutable derived deliverables; autosave backups are neither.
A checkpoint must coordinate both DCC saves and USD publication; copying files
while the applications are writing is not a consistent snapshot.
Use Git for code/config; consider LFS or object storage for large binary assets.
Keep authored assets and look layers durable; only .bridge is disposable.

Verified: OpenUSD composition opens; exactly one imported mesh; Blender dimensions
0.0200000014 m per side. This is a smoke test, not a repeat-sync implementation.
