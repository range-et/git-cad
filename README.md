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

## Run V1

```sh
uv sync --extra dev --extra mcp
uv run cad-git demo demo-project
uv run cad-git --project demo-project ui
```

On this Mac, double-click **Open CAD-GIT.command** to open the existing demo.
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

## Current boundaries

This is a working first prototype, not completion of every acceptance criterion
in the [review specification](docs/SPECIFICATION.md).

- Rendered preview uses three studio lights, a neutral reflection environment, USD preview surface values, ambient occlusion. It does not evaluate Cycles graphs, shader displacement, or a full USD renderer.
- Rhino capture tessellates meshes, Breps and convertible extrusions using Rhino; blocks are expanded in save captures. Unsupported geometry rejects capture. Classic Rhino materials and renderer content are not yet transferred by this capture path.
- USD-to-Rhino handoff creates polygon meshes in millimeters, preserving object/source identifiers and known material revision slots. It does not reconstruct editable NURBS, constraints, or feature history.
- Blender graph assets can be archived and rebound to whole objects in new Blender files. Per-face native graph restoration and general renderer interchange are unfinished. Native material evaluation belongs to its application.
- Assembly placement samples time zero. Animation, complex instancing and reset-transform subtrees have limitations or explicit rejection. This is a static polygon assembly/inspection workflow.
- STL uses authored polygon geometry, with unit conversion and topology checks. It does not evaluate renderer displacement, perform boolean unions, or certify wall thickness or self-intersections. Subdivision base-mesh export requires acknowledgement.
- Reference adapters are bundled Python hooks. The inbox capture contract and configurable external application commands provide extension points; a general third-party plugin registry is not implemented yet.
- Native editable histories are not archived. USD snapshots preserve exportable scene states, and Blender material libraries preserve captured shader graphs. Restoring a USD snapshot cannot restore every native-only modeling feature.

## Review and hardening

Two independent architecture and UI/UX reviews produced fixes for capture recovery, archive integrity, safe publication, project ownership, draft preservation and asynchronous UI failures. See [findings, fixes and remaining work](docs/REVIEWS_AND_HARDENING.md).

## Verification

```sh
uv run pytest -q
uv run python tests/integration/cli_smoke.py
uv run python tests/integration/ui_smoke.py
uv run python tests/integration/ui_robustness.py
```

The second check opens a temporary Qt/VTK project and exercises four viewport modes,
two source tabs, mesh selection, assembly preview and immutable assembly creation.
It requires a graphical session. Native integration checks and their scope are
recorded in [V1 implementation notes](docs/V1_IMPLEMENTATION.md).

Deferred design topics are tracked in [Future features and open questions](docs/FUTURE_FEATURES_AND_OPEN_QUESTIONS.md), including native editability across application round trips. These are outside current V1 scope.

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
