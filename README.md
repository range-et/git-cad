# CAD-GIT

A fully local USD snapshot history and assembly tool implemented in Python.
Rhino and Blender keep their normal working files. Each tracked save exports a
new timestamped USD snapshot; the first-release UI lets the user browse history,
select objects from any snapshots, and compose a reusable USD result on `main`.
The core feature is file/scene lineage and assembly, without per-vertex merging.
Selected historical USD parts or assemblies can be exported directly as STL print
artifacts, without reopening the native applications.
The UI uses PySide6, a PyVista/VTK inspection viewport, and the Monad System theme;
the reference OpenUSD SDK handles scene composition and preservation.
Geometry and historical materials can be selected independently. The project
material library can retain native shader assets alongside portable previews and
separate engineering data, with all assignments pinned to exact revisions.

Source histories advance independently. Main changes only when the user chooses a
saved assembly. Native applications can import that result and continue working;
CAD-GIT does not automatically rewrite or synchronize their native documents.
AI agents are optional, and all required work happens locally through CLI/UI.

## Project tracking

[features.md](features.md) lists implemented capabilities and completion history.
[issues.md](issues.md) tracks open defects, investigations and future ideas.
[AGENTS.md](AGENTS.md) defines how these documents stay current with the code.

## Run V1

```sh
uv sync --extra dev --extra mcp
uv run cad-git demo demo-project
uv run cad-git --project demo-project ui
```

On this Mac, double-click **Open CAD-GIT.command** to open the existing demo.
The app uses a bundled CAD-GIT cube/history icon for its window and macOS Dock.
Its editable SVG and PNG/ICNS assets live in `src/cadgit/resources/`;
run `uv run python scripts/build_icon.py` to regenerate the raster assets.
The initial engine studies are generated sample geometry, identified in their
snapshot metadata. Later captures in this local demo include native application
integration checks.

1. Click a commit in **Versions & branches** to open its whole-file snapshot. Compact Git-style columns with straight tracks and short adjacent-column hops show save ancestry, branch forks, imports and assembly inputs. Branch heads, the selected main result and named versions appear on their nodes. Right-click a commit for actions.
2. Choose **Wireframe**, **Shaded**, **Rendered preview**, or **X-ray**. Use **Edges** for an overlay.
3. Click a mesh, or select meshes/groups in the object tree. Selected geometry gets an edge highlight; click empty viewport space to clear it. Drag to orbit without clearing selection. **Add selected to assembly** collects those pieces.
4. Switch tabs and collect other pieces. **Preview assembly** opens the combination in another tab.
5. **Save assembly as USD** writes a new immutable assembly and exports a USD file. **Set as main** deliberately selects the project result.
6. **Open with** creates a new ordinary `.blend` or `.3dm` working file. Application targets are editable in **Settings**. Other applications can be configured with an argument-list command receiving `{usd}`.
7. Select a graph node and use **Branch…** or **Name version…**. Right-click a branch head to use it for subsequent saves. Changing the capture branch does not replace native document contents; use **Open with** to resume an old state in a new file.

Drag the dividers to resize the history sidebar, viewport, inspector, assembly tray, and the inspector’s object/details sections. Window geometry and pane sizes are remembered per project.

USD reading, texture packing and mesh preparation run in background workers
(at most two scene loads at once). The viewport installs prepared objects in
short batches with an object counter, then renders the completed scene. Closing
a tab cancels pending preparation/upload work. GPU uploads and rendering still
use the GUI thread; exceptionally large individual meshes or expensive rendered
frames can still pause interaction. See [viewport loading notes](docs/VIEWPORT_LOADING.md).

**Watch native saves** attaches the bundled hooks through the running community
Blender MCP listener (localhost:9876) and Rhino listener. It starts a local inbox
service. Native application saves remain ordinary saves. Hooks capture a full USD
scene and the service commits it into history. Reconnect after restarting an
application. An AI agent is not required; the CLI talks to the listeners directly.
The current reference integrations target macOS and use a POSIX local service lock.

```sh
uv run cad-git init /path/to/project
uv run cad-git -p /path/to/project begin --rhino-endpoint http://127.0.0.1:10500/
uv run cad-git -p /path/to/project ingest scene.usdz --source blender
uv run cad-git -p /path/to/project log --source blender
uv run cad-git -p /path/to/project snapshot --source rhino
uv run cad-git -p /path/to/project import main --app blender --output source/new-study.blend
uv run cad-git -p /path/to/project export main --output print.stl --units mm
uv run cad-git -p /path/to/project autosnapshot on --interval 300
uv run cad-git -p /path/to/project stop
```

CLI output paths are relative to the current shell directory. `--project` selects
the history store, and must precede the subcommand. `import` creates a new native
file and refuses to overwrite an existing one. Use `--no-launch` to create it
without opening an application. `mcp` optionally exposes the same core operations
over stdio; each initialized project includes an example configuration.

## Agent-agnostic skill

[skills/cad-git/SKILL.md](skills/cad-git/SKILL.md) explains the implemented tool and
safe onboarding of an existing CAD folder. It includes native-capture and offline
USD workflows, command references, and a read-only folder inventory helper.
Any agent can read that file directly; no particular AI client or MCP setup is
required. Example request: “Read this checkout's skills/cad-git/SKILL.md and onboard
my existing design folder, preserving its native files.” The skill folder can also
be copied into an agent's supported skill-discovery location; it is not installed
globally by this repository.

Porting now includes the separate [materials and assets portbook](skills/cad-git/references/material-library.md): classify scene versus shader files, register images/specifications, record sourced physical data, pin dependencies, and verify native appearance separately from file integrity.

## Materials & Assets

Switch to **Materials & Assets** at the top of the window. Browse project-wide
materials, images, shader libraries and documents; select an item and its exact
revision to inspect properties, dependencies, lineage and source/license details.
Import assets, create/revise a material, or recombine physical and appearance
facets from two historical materials. **Use for new pieces** returns to Geometry
with that revision selected for subsequently added assembly pieces.

Images and documents have their own stable identities and immutable revisions.
Updating an image does not change materials that reference its older revision.
Physical values require units and sources; unknown values remain unspecified.
**Browse Poliigon** opens the provider site; V1 imports local downloads rather
than providing an authenticated catalog integration.

```sh
uv run cad-git -p /path/to/project library list
uv run cad-git -p /path/to/project library import /path/to/color.png --kind image
uv run cad-git -p /path/to/project library show REVISION_ID
uv run cad-git -p /path/to/project library verify REVISION_ID
```

See the [implemented scope and limits](docs/MATERIAL_LIBRARY_V1.md) and
[material review results](docs/MATERIAL_LIBRARY_REVIEW.md).

## Storage and lineage

```text
project/
  cadgit.json                  # project settings and active capture branches
  source/                      # ordinary editable native working files
    study.blend
    study.blend.cadgit.json    # ancestry of a CAD-GIT-created working file
  history/
    sources/<app>/<snapshot>/  # immutable manifests and self-contained scene.usdz
    events/                    # main selections, branches, handoffs, failures
  assemblies/<id>/             # pinned recipe, material bindings, scene.usdz
  main/                        # selected assembly pointer and convenience USD
  materials/<revision>/        # native Blender graph library and archived images
  library/revisions/<revision>/ # logical materials, images, shaders and documents
  artifacts/prints/<id>/       # STL, validation report and source provenance
  .cadgit/                     # disposable runtime state, inbox, logs, draft tray
```

History captures full scenes. Assembly recipes reference exact snapshot IDs and
USD prim paths. A new native working file gets a lineage sidecar and an event;
subsequent tracked saves include its `imported_from` ancestry. Native applications
need no knowledge of commits. Keep a generated sidecar with its native file when
renaming or moving it. Copying a native file without its sidecar does not preserve
this ancestry automatically.

Commits use staged writes, content hashes, a commit marker, and a local writer lock.
Missing USD dependencies reject capture. Failed capture leaves the working file
and existing history intact and retains diagnostics in the inbox. Durable history
is kept outside the ignored runtime directory. The generated Git rules mark native
formats as binary; Git storage and recovery remain separate concerns.

## Data compatibility

The format evolves additively: new optional parameters preserve existing IDs, meanings and defaults. Unknown fields survive validation and known-field updates; unsupported required behavior is rejected explicitly. Old history is never rewritten on open. See the [data compatibility contract](docs/DATA_COMPATIBILITY.md) and its frozen V1 regression fixtures.

## Optional B-rep jobs

**Prepare B-rep job…** archives per-part mesh inputs and lineage from a saved
version for future DualBrep reconstruction. `cad-git brep prepare` provides the
same workflow; `cad-git brep doctor` checks a separately configured CUDA runtime.
This release prepares inputs only: no model inference or STEP generation is
enabled yet. Preparation works without CUDA; Apple Silicon inference requires a
backend port and validation. See [setup, limitations and the Metal port plan](docs/DUALBREP.md).

Reconstruction itself is outside the core product scope. The separate
[DualBrep fork](https://github.com/range-et/DualBrep) may provide an optional Docker
service later; CAD-GIT would submit jobs and track results, or report that no
compatible runtime is available. That service integration is not implemented yet.

## Current boundaries

This is a working first prototype, not completion of every acceptance criterion
in the [review specification](docs/SPECIFICATION.md).

- Rendered preview uses three studio lights, a neutral reflection environment, USD preview surface values and image textures, and ambient occlusion. Base color, roughness, metallic and opacity maps are supported, including packaged USDZ images and indexed UVs. Missing UVs use labeled box mapping for inspection only. It does not evaluate Cycles graphs, normal/displacement maps, or a full USD renderer.
- Rhino capture tessellates meshes, Breps and convertible extrusions using Rhino; blocks are expanded in save captures. Unsupported geometry rejects capture. Classic Rhino materials and renderer content are not yet transferred by this capture path.
- USD-to-Rhino handoff creates polygon meshes in millimeters, preserving object/source identifiers and known material revision slots. It does not reconstruct editable NURBS, constraints, or feature history.
- Blender graph assets can be archived and rebound to whole objects in new Blender files. Per-face native graph restoration and general renderer interchange are unfinished. Native material evaluation belongs to its application.
- Assembly placement samples time zero. Animation, complex instancing and reset-transform subtrees have limitations or explicit rejection. This is a static polygon assembly/inspection workflow.
- STL uses authored polygon geometry, with unit conversion and topology checks. It does not evaluate renderer displacement, perform boolean unions, or certify wall thickness or self-intersections. Subdivision base-mesh export requires acknowledgement.
- Reference adapters are bundled Python hooks. The inbox capture contract and configurable external application commands provide extension points; a general third-party plugin registry is not implemented yet.
- Native editable histories are not archived. USD snapshots preserve exportable scene states, and Blender material libraries preserve captured shader graphs. Restoring a USD snapshot cannot restore every native-only modeling feature.

## Review and hardening

Two independent architecture and UI/UX reviews produced fixes for capture recovery, archive integrity, safe publication, project ownership, draft preservation and asynchronous UI failures. See [findings, fixes and remaining work](docs/REVIEWS_AND_HARDENING.md).

A subsequent three-agent architecture, UX and QA pass fixed material identity,
preview accuracy, settings recovery and failed exports/imports. See the
[compiled review and validation](docs/REVIEW_2026-11-08.md).
The [post-texture recheck](docs/REVIEW_2026-11-08_ROUND_2.md) records the next
three-agent pass, including inherited UVs, initialization failures and preview diagnostics.

## Verification

Follow [build/review gates](docs/BUILD_GATES.md) and the repository's
[agent instructions](AGENTS.md). The repeatable candidate check is
`uv run python scripts/check.py --build --ui --mcp` in a graphical session
with the development and MCP extras installed.
The [UX action/state matrix](docs/UX_TEST_MATRIX.md) tracks tested workflows and
explicit coverage gaps. It records per-check logs and a JSON report under ignored `build/qa/`.
CI runs core/build gates; independent reviews and applicable GUI/native checks
are recorded separately using the [review template](docs/REVIEW_TEMPLATE.md).

```sh
uv run pytest -q
uv run python tests/integration/cli_smoke.py
uv run python tests/integration/ui_smoke.py
uv run python tests/integration/ui_robustness.py
uv run python tests/integration/material_library_smoke.py
uv run python tests/integration/viewport_responsiveness.py
uv run python tests/integration/texture_preview_smoke.py
```

The UI smoke check opens a temporary Qt/VTK project and exercises four viewport modes,
two source tabs, mesh selection, assembly preview and immutable assembly creation.
It requires a graphical session. Native integration checks and their scope are
recorded in [V1 implementation notes](docs/V1_IMPLEMENTATION.md).

Open work and deferred ideas are tracked in [issues.md](issues.md). The [native editability design note](docs/FUTURE_FEATURES_AND_OPEN_QUESTIONS.md) preserves background on application round trips; it is not a second backlog.

See also the [historical OpenUSD/Rust assessment](docs/USD_ARCHITECTURE.md),
[related asset managers](docs/RELATED_SYSTEMS.md), and
[materials and lineage design](docs/MATERIALS_AND_LINEAGE.md).

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE).

Use, modification, and distribution are permitted for the purposes specified in
the license, including noncommercial purposes. Commercial uses outside those
permissions require a separate license from the copyright holder.

This is source-available software. The license does not require disclosure of
source code for distributed modifications. See [LICENSE](LICENSE) for the full
terms.
