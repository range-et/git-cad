# Onboard an existing design folder

The outcome is an initialized geometry and asset history store linked to real
user files, with verified geometry baselines and material/image/spec revisions
when those inputs are available. This does not recover
unrecorded native history or automatically combine all files into main.

## 1. Inspect without reorganizing

Establish the tool checkout/executable and the folder the user wants to onboard.
Use the read-only helper to find native files, USD exports, other exchange assets,
textures, shader libraries, material specifications, existing project config and initialization collisions:

```sh
python3 "/path/to/this/skill/scripts/inspect_folder.py" "/absolute/path/design-folder"
```

The helper reads names/config only; it does not open or export native documents.
Its JSON is an inventory, not a validation of CAD-GIT data or native dependencies.
Review the reported files and any unreadable paths. Follow existing references to
external assets without moving them. Classify `.blend` files as native working
scenes or shader libraries; do not open every graph library as a model. Inventory
material specifications and provider/license evidence alongside texture files. Choose the intended base files, not every
backup or similarly named experiment. Ask for the choice only if it cannot be
inferred from the user's request and available context.

If `cadgit.json` is present, or the helper finds a nested project config, run
`status` against the intended existing project root before creating another one. An older `bridge.json` is not a current project. Keep it in place.

## 2. Choose a safe project root and initialize

An existing folder can itself be the project root when it has no conflicting
reserved paths. If it already has `history/`, `main/`, `materials/`, `artifacts/`,
`assemblies/`, `library/`, `.cadgit/` or `mcp.example.json` unrelated to CAD-GIT, choose a new
child such as `cad-project/`. Native assets can stay outside that child.

For example, keep this existing layout:

```text
design-folder/
  models/engine.3dm
  animation/engine.blend
  usd/previous-export.usdz
  textures/
  materials/                     # already used by the user's workflow
```

Add a new history store at `design-folder/cad-project/` instead of taking over
`materials/`. No copying or moving of the model files is necessary.

```sh
CADGIT_TOOL_ROOT="/absolute/path/to/git-cad"
CADGIT_BIN="$CADGIT_TOOL_ROOT/.venv/bin/cad-git"
CADGIT_PROJECT="/absolute/path/design-folder/cad-project"

# Only if the tool environment has not been installed:
# uv sync --project "$CADGIT_TOOL_ROOT" --extra mcp

"$CADGIT_BIN" init "$CADGIT_PROJECT" --name "Engine project"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" status
```

Inspect the generated config/Git rules. CAD-GIT adds rules at its selected project
root; a Git ignore rule higher in the existing repo can still hide that child.
Do not stage or commit the user's files unless requested. Stop if initialization
reports a collision; use a different empty root rather than deleting the conflict.

## 3. Record actual baselines

### Native Rhino/Blender files

Have the chosen `.3dm` and/or `.blend` open in their applications, with the community
listeners enabled. Confirm which document is active before binding capture. Do not
close unrelated documents, change their working paths or save their edits just
because a project was initialized.

If a known previous CAD-GIT project is being replaced, stop that project's watcher
first. Do not stop arbitrary projects. `begin` explicitly switches the application's
CAD-GIT binding to this project; hooks do not watch all files on disk.

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" doctor
"$CADGIT_BIN" -p "$CADGIT_PROJECT" begin
```

Read each app's result. If an app is unavailable, record that limit and continue
with independent work. Do not claim an app is connected merely because the
service started. Use an explicit known `--rhino-endpoint` if discovery is ambiguous.

The user's next ordinary Save creates a baseline capture. If the requested task
needs a snapshot now, this captures current state without a native Save:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" snapshot --source rhino
"$CADGIT_BIN" -p "$CADGIT_PROJECT" snapshot --source blender
"$CADGIT_BIN" -p "$CADGIT_PROJECT" log --source rhino
"$CADGIT_BIN" -p "$CADGIT_PROJECT" log --source blender
```

Run only the snapshot commands for the selected available apps. Label/report a
manual snapshot's potentially unsaved state truthfully. Rhino may finish exporting
on Idle; check history after it becomes idle instead of repeatedly creating new
captures. Use `status` and retained inbox errors when a capture fails.

### Existing USD exports, including offline onboarding

No native application is needed to import a valid USD baseline:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" ingest \
  "/absolute/path/design-folder/usd/previous-export.usdz" \
  --source manual --label "Existing USD baseline: previous-export.usdz"
```

Use a native source label only when its provenance is known. An imported baseline
is captured history from now onward, not a reconstruction of earlier editing
steps. Do not feed `.3dm`, `.blend`, STEP or STL directly to `ingest`; obtain a USD
export through a supported native adapter or an explicit application export.
Keep dependencies available while ingesting; unresolved dependencies reject capture.

For each returned or newly listed snapshot ID:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" show SNAPSHOT_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" verify SNAPSHOT_ID
```

Confirm the expected source, native path when captured by an adapter, branch,
trigger, warnings and successful verification. Do not edit manifests to disguise
missing lineage. Historical native file versions are not archived by this process.

## 4. Port the material and asset library

Read [material-library.md](material-library.md) when images, graphs, documents or
material properties exist. Import chosen assets independently, create explicit
logical material definitions, pin revision dependencies, and verify each revision.
Do not infer one material per image or engineering values from a file's name.
The materials workspace is a separate browser, not the geometry inspector's old
captured-shader dropdown. Existing captured native shaders remain available.

An otherwise usable geometry project can be handed off while an unavailable
native renderer or missing property source is clearly marked incomplete. Do not
invent data to make the material catalog look complete.

## 5. Open the workflow and compose only when requested

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" ui
```

The user opens baseline versions in tabs, picks geometry, adds pieces to the draft,
and saves a new USD assembly. Inspect real prim paths and exported content before
claiming the result is correct. Only select main when a specific assembly is
accepted; empty main is a valid onboarding result. Use the command reference for
headless composition, exports, branch operations and new native working files.

Do not run `demo` inside the user's project to fill an empty graph. Generated
engine history is useful in a separate throwaway project for learning, not as the
user's captured data. The legacy `test/` fixtures in the checkout demonstrate
exchange assets; the current `demo-project/` workflow is generated through `demo`.
Neither should be copied wholesale as a migration.

## 6. Hand off a usable project

Provide a concise summary containing:

- Tool executable and initialized project root.
- Original base-file locations and the active app/branch bindings, if connected.
- Verified baseline snapshot IDs, plus assembly/main/output IDs if actually created.
- Material identities and exact material/image/graph/document revision IDs, including
  source URLs/license status, physical-data sources/unknowns, and renderer validation.
- Any appearances still using captured native overrides instead of the approved
  library graph; do not silently revise materials or replace those edits.
- Working start/UI/stop commands with this project's actual path.
- Unavailable apps, capture warnings, or user choices still needed.

Reconnect with `begin` after application restarts. Timed tool snapshots are optional
and disabled by default; enable them only when requested. To end this watch session:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" stop
```
