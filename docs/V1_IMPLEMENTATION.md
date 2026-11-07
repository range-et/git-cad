# V1 implementation and verification

The running application is the Python implementation in `src/cadgit`. The CLI,
optional MCP server, background ingester, and Qt UI share the same project store
and USD operations. The current workbench entry point is `ui_v2.py`; `ui.py` still
supplies shared theme/widget/worker helpers and contains the earlier UI prototype.

## Native-file handoff contract

The manager owns history and lineage. Rhino and Blender receive ordinary new
files. Creating a working file writes a `<native-file>.cadgit.json` ancestry
sidecar and a durable `native_handoff` event. Save hooks read that sidecar and
include the source snapshot or assembly ID in the next capture. An assembly recipe
records which exact prim was selected from each input snapshot and optional pinned
material revision. History can therefore zigzag between software without either
native application implementing commit semantics.

The application does not silently append an imported assembly to the user's active
Blender scene. The built-in Blender handoff imports in an isolated background
process, restores supported historical whole-object material graphs, saves a new
blend, and opens that working file with the save hook. Rhino handoff writes a new
3dm containing USD-derived meshes and opens it as a normal document. An attached
Rhino hook recognizes generated documents through the project sidecar.

Renaming native files requires retaining/renaming the associated sidecar. Hook
installation is session-scoped. The CLI can operate without an AI agent, but the
reference live-app hooks currently require the community listeners to be running.
Standalone installable application add-ons remain packaging work.

## Checks performed on 2026-11-07

- Eleven automated core tests passed: immutable source history and deliberate main,
  unit/up-axis/world-transform conversion, source corruption detection, unresolved
  asset rejection, preservation of existing Git configuration, direct STL source
  fidelity, ordered inbox ingestion, branch ancestry, native Rhino handoff lineage
  and dimensions, invalid-target failure, and inherited material revision identity.
- The graphical integration check opens multiple whole-file tabs, exercises all
  four viewport modes, adds geometry from two snapshots, previews the assembly,
  and creates a verified immutable assembly with both source selections retained.
- An isolated Blender process installed the save hook, saved a native working file
  twice with different cube positions, and produced distinct USD save captures.
- Two real Rhino saves of the project calibration cube, moved 10 mm between saves,
  produced USD mesh centers 10 mm apart. The hook serializes an exact in-memory
  native staging copy at EndSave, then tessellates an isolated document on Idle.
  Earlier attempts using Rhino's USD writer on a headless document cancelled;
  the final capture path uses Rhino tessellation and writes mesh USD directly.
- A Rhino mesh assembly with an older Blender Noise → ColorRamp → Principled graph
  was imported in an isolated Blender process. Four native graph nodes survived;
  an isolated Cycles render completed. This validates that specific native graph
  path, not arbitrary graph interchange or engineering material providers.
- The new native handoff path created a separate Blender working file from the
  graph-bound assembly. The original live Blender document was not modified by
  those isolated tests.

Temporary probe logs and older failed inbox entries remain local diagnostics.
Generated demo scenes are tagged as sample data. Refer to README for supported
behavior and current limitations; the full specification includes future work.

## Graph, layout, and viewport refinement

The sidebar now draws the ancestry DAG from recorded parents, native imports and
assembly inputs. It includes branch forks and heads, named version bookmarks, and
the selected main result. Search dims unrelated commits while retaining topology.
Named versions are immutable-record bookmarks stored in project configuration and
recorded as history events.

Horizontal and vertical splitters resize the workbench columns, assembly tray,
and inspector sections. Qt settings remember window geometry and splitter states
per project. The graphical smoke test exercises actual divider drags, graph-node
clicks and persisted pane state. Fourteen core tests pass, including DAG ancestry
and named version behavior.

Loading a scene cleared VTK's light kit. The corrected viewport reinstalls three
studio lights after each load and adds reflection fill, PBR surface values,
ambient occlusion in rendered preview. Visual inspection used
the engine assembly. Inspection lighting does not change export geometry.

The current Rhino–Blender–Rhino return path produces meshes. Native editability
and optional native version archives are deferred design questions, not V1 release
requirements. See [Future features and open questions](FUTURE_FEATURES_AND_OPEN_QUESTIONS.md).

The default ground plane has been removed. Clicking empty viewport space clears
mesh and object-tree selection and removes selection edges. Camera drags preserve
selection; the graphical smoke test exercises mesh clicks, blank-space clicks,
and drags.

## Additive format contract

[Data compatibility](DATA_COMPATIBILITY.md) is now an explicit V1 requirement. Typed
records preserve extra fields; existing V1 records default to minor version zero.
Project and record loading gate unsupported major formats and required features.
Writers recheck configuration compatibility under the project lock. Known edits
preserve unrelated configuration/main-pointer fields, and immutable records remain
unchanged on open. Frozen V1 fixtures and regression tests cover old-data reuse,
unknown JSON and USD properties, material extensions and safe rejection.
