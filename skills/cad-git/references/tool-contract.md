# Implemented tool contract

## What the tool stores

| Item | Meaning |
| --- | --- |
| `cadgit.json` | Project identity, active capture branches and settings. |
| `history/sources/<source>/<snapshot>/` | Immutable scene package, manifest, hashes and commit marker. |
| `history/events/` | Commit, branch, main-selection, handoff and other events. |
| `assemblies/<id>/` | Saved USD assembly, exact input selections and pinned material bindings. |
| `main/current.json` | Authoritative selected assembly ID. `main/scene.usda` is its recoverable convenience projection. |
| `library/revisions/<revision>/` | Immutable logical materials, images, graphs and specs; `library/library.json` binds ownership to this project. |
| `materials/<revision>/` | Archived native shader assets and known image dependencies. |
| `artifacts/prints/<id>/` | Registered STL, provenance and topology report. |
| `.cadgit/` | Ignored runtime, inbox, diagnostics and draft state. Failed/pending captures may be needed for recovery. |

The GitHub repository is `range-et/git-cad`; the executable is `git-cad`. There is
no requirement to create a Git repository, commit binaries, push to a remote, or
use an AI agent. The example `test/bridge.json` in the tool checkout predates the
current runtime. Do not copy its configuration or software-ownership assumptions
into a new project. `git-cad demo` creates generated sample history, not a port of
the user's files.

## CLI conventions

Examples use `CADGIT_BIN` for the absolute executable and `CADGIT_PROJECT` for the
initialized project directory. Re-establish these variables in a fresh shell.
`-p/--project` precedes the subcommand. Paths passed as input/output are resolved
relative to the shell's current directory, not automatically under `--project`.
Prefer absolute paths during onboarding.

```sh
"$CADGIT_BIN" init "$CADGIT_PROJECT" --name "Engine study"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" status
"$CADGIT_BIN" -p "$CADGIT_PROJECT" doctor
"$CADGIT_BIN" -p "$CADGIT_PROJECT" begin
"$CADGIT_BIN" -p "$CADGIT_PROJECT" snapshot --source rhino
"$CADGIT_BIN" -p "$CADGIT_PROJECT" ingest "/absolute/path/export.usdz" --source manual --label "Existing USD baseline"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" log --source rhino
"$CADGIT_BIN" -p "$CADGIT_PROJECT" show SNAPSHOT_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" verify SNAPSHOT_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" ui
"$CADGIT_BIN" -p "$CADGIT_PROJECT" stop
```

`init` reuses an existing valid project. Fresh initialization rejects collisions
with its reserved paths; it does not relocate existing assets. Source/branch
identifiers use letters, digits, `_` and `-`.

`doctor` reports environment and connection diagnostics; it does not certify the
chosen native document or a successful capture. `begin` reports each adapter's
result separately and may start ingestion with an app unavailable. `snapshot`
exports the current app state, which can include unsaved edits; it is not a native
Save. Rhino's save-hook export can wait for Idle, so an immediate zero capture
count is not proof of failure. Check history after the application becomes idle.
Do not retry snapshot creation in a tight loop.

## Assembly and continuation

Inspect real prim paths through a snapshot tab's object tree or the MCP
`inspect_snapshot` operation. The CLI does not have a `merge` or `checkout`
command. In the UI: open whole-file versions in tabs, select meshes/groups, add to
the draft, preview, then save a new USD. Setting main is a separate deliberate
operation. CLI equivalents are:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" compose \
  --input "SNAPSHOT_A:/World/ActualPart" \
  --input "SNAPSHOT_B:/Scene/ActualGroup" --name "Selected assembly"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" verify ASSEMBLY_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" export ASSEMBLY_ID \
  --format usdz --output "/absolute/path/new-assembly.usdz"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" main set ASSEMBLY_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" import ASSEMBLY_ID \
  --app blender --output "/absolute/path/new-working-file.blend"
```

Use the IDs returned by the tool, never the literal example names. These prim
paths are illustrative; Rhino and Blender exports need not use either hierarchy.
`import` creates a new file; `--no-launch` prepares it without opening the app.
The UI's **Open with** targets can be configured. Outputs refuse overwrite.
Prefer `.usdz` when a self-contained USD package is wanted. Plain USD exports can
retain references to project assets. CLI USD export writes the scene/package;
the UI assembly-save action and native `import` additionally create lineage
sidecars. Do not assume a manually exported USD has such a sidecar.

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" branch create experiment \
  --source rhino --from SNAPSHOT_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" branch use experiment --source rhino
"$CADGIT_BIN" -p "$CADGIT_PROJECT" export ASSEMBLY_ID \
  --format stl --units mm --output "/absolute/path/part.stl"
```

Branch commands change bookkeeping for future captures, not the open native
geometry. STL uses authored meshes, not rendered pixels or shader displacement.
Units are explicit; open/nonmanifold and subdivision-base-mesh cases need deliberate
handling. Do not add `--allow-issues` or `--allow-base-mesh` merely to force success.
Exports do not certify a part's printability.

## Adapter and fidelity boundaries

The current reference adapters target macOS with the community Blender listener
at localhost:9876 and a discoverable Rhino listener. An explicit Rhino endpoint
can be supplied to `begin --rhino-endpoint URL` when the intended document is known.
Do not guess that an endpoint selects the correct file. Native capture lanes are
currently application-plus-branch, not independent per-document IDs. Bind one
chosen working document per app; do not imply that opening a folder automatically
watches every `.blend` or `.3dm` in it. Reconnect after an application restart.

Rhino export/return uses polygon meshes; NURBS reconstruction and native-version
archives are deferred questions. Blender whole-object graph assets can be archived
and restored, including shared materials; per-face native restoration is not
supported. The inspection viewport does not evaluate Cycles graphs. Material
slots/revisions and future engineering properties are separate from geometry
lineage. Static placement samples time zero; unsupported complex content needs
explicit review rather than a promise of complete animation/native editability.

## Materials & Assets

Use [material-library.md](material-library.md) for the independent library API and
porting procedure. `library verify` validates asset/material revision IDs; the
older top-level `verify` resolves geometry snapshots/assemblies. Logical material
assignments use `library_material_revision`, separate from a captured native
`material_revision`. Native captures retain edited appearance per prim; they do
not silently overwrite it from an older library graph.

## Optional MCP

With the `mcp` extra installed, run:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" mcp
```

Use the project's generated `mcp.example.json` if the user wants their agent client
connected. Client configuration is agent-specific and is not required by this
skill. Do not edit global client configuration just to run the CLI workflow.
The current MCP operations are `project_status`, `history`, `inspect_snapshot`,
`ingest_usd`, `create_assembly`, `select_main`, `export_print`, `list_materials`, and
`verify`. Initialization, adapter startup, branch operations and native handoff
remain available through the CLI. Library operations additionally expose
`library_list`, `library_revision`, `library_history`, `library_import`,
`library_material`, `library_recombine`, `library_verify` and `library_used_by`.
Use these for first-class logical materials/assets rather than treating
`list_materials` (legacy captured shaders) as the full project library. AI client's MCP access and native-app listeners
are separate connections.

## Optional B-rep preparation

`git-cad -p PROJECT brep prepare REF [--select /Prim]` creates a committed input
bundle under `artifacts/brep_jobs/`. `brep list/show/verify` inspect these jobs.
`brep doctor --python BACKEND_PYTHON --checkout DUALBREP` probes an external optional
runtime; launch environment variables `CADGIT_DUALBREP_PYTHON` and
`CADGIT_DUALBREP_CHECKOUT` also work. No models are downloaded.

Preparation is not conversion: no STEP/NURBS result exists yet, and
`execution_available` is false in this release. CUDA prerequisite readiness is
not end-to-end validation. Never claim Metal/CPU support from PyTorch availability
alone. Preserve job units and inverse normalization; do not import upstream's
normalized output as millimeters. Disconnected meshes require explicit
`--split-components`; nested shells may represent cavities. Subdivision base-mesh
preparation requires `--allow-base-mesh`. Do not auto-enable these flags to bypass
a modeling decision. See the repository's `docs/DUALBREP.md` for the future runtime
and qualification contract. Ordinary Rhino handoff still produces meshes.

### Print artifact verification

`verify` also accepts the exact `print_…` artifact ID returned by STL export.
Print artifacts are not scene references for composition, native handoff or main.
Abbreviated artifact IDs are not supported. Verification checks archived bytes and
metadata; it does not certify printability or native renderer fidelity.
