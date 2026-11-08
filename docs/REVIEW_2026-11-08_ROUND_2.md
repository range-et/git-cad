# Architecture, UI/UX and QA recheck — 2026-11-08

This repeats the three-agent review against the current checkout after the texture-rendering implementation. The architecture agent checked USD composition and appearance semantics; the UI/UX agent played through real Qt/VTK windows and inspected screenshots; QA ran the core/CLI baseline and failure probes. The parent integrated the findings and checked the final shared tree. Earlier base-tool review fixes were preserved. Reconstructed-lineage annotations are excluded from this release.

## Findings and disposition

| Priority | Reproduced problem | Change and regression evidence |
| --- | --- | --- |
| P1 | Selecting a child mesh whose UV primvar was inherited from its parent lost that mapping during assembly composition. The saved version silently used box mapping although hash verification passed. | Materialize inherited primvars on the selected subtree root before composition; retain indexed values and unknown metadata. Compare source and saved texture coordinates and verify both records. |
| P2 | Parent-authored display color appeared as fallback gray in the source, then changed after assembly composition materialized it. | Resolve inherited/indexed display colors at the requested sample time and compare source/saved colors in a regression. |
| P1 | Initialization published `cadgit.json` before checking an existing `source` file, directory-valued Git rules, or non-text Git rules. Init failed, but the folder subsequently opened as an initialized project. | Preflight existing source/Git-rule paths and readable text before publication. Failure probes require no new project scaffolding and unchanged original files. |
| P2 | Shader colors and scalar properties used the default USD time while geometry and UVs used the requested sample time. A time-sampled material could fall back to gray/default roughness. | Sample appearance values at the same explicit time as geometry; compare authored time-zero and later material samples. Static assembly limitations remain unchanged. |
| P2 | Malformed texture file input types could raise an uncaught attribute error and fail an entire snapshot load. | Validate asset values and retain geometry with an actionable texture warning. |
| P2 | Scaling a valid 8192×1 image for preview could produce a zero-height image and reject it. | Keep preview dimensions at least one pixel while bounding GPU resolution. |
| P2 | Packing a low-resolution base-color map with a detailed opacity mask reduced both to the color map's resolution; a checker mask could make the entire object disappear. Roughness/metallic packing had the same detail loss. | Pack each map group at its largest input width and height, within the existing preview cap. Regression checks preserve the detailed alpha and metallic channels. |
| P2 | A texture-only material was labeled “Physical-only / no portable preview,” and its card claimed no color preview despite rendering correctly. | Identify image-backed appearances and use their pinned base-color image for browser previews where available. Keep native-only and physical-only states distinct. |
| P2 | Long preview warnings clipped at minimum window size; selecting geometry replaced the details containing the remaining warnings. | Provide compact warning status and a persistent way to inspect the complete warning list independently of selection details. |
| P2 | Integrity verification read each archived payload into memory at once, which scales poorly for large native shader libraries. An unreadable payload also escaped as an exception. | Stream payload hashes in bounded chunks and report read failures as verification errors. A regression forbids whole-payload buffering and injects a read failure. |
| Polish | Image previews could crop when the inspector shrank, and very thin image thumbnails could scale to zero pixels. | Fit inspector images within their current bounds and clamp thumbnail dimensions to at least one pixel. |

## Verification

Counts exclude the eight separate reconstructed-lineage annotation tests.

Baseline before this pass:

- **122 pytest tests passed**.
- CLI smoke passed: init, ingestion, assembly composition, main selection, USD/STL export, new Rhino file with lineage, and verification.
- All four graphical suites passed: `ui_smoke.py`, `ui_robustness.py`, `material_library_smoke.py`, and `texture_preview_smoke.py`.

After the fixes, the parent reran the shared tree: **140 pytest tests passed**,
CLI smoke passed, and `git diff --check` was clean. This adds 18 core regression
cases beyond the baseline, alongside expanded graphical regressions.

All four graphical suites passed during the review. After the final fixes,
`material_library_smoke.py`, `texture_preview_smoke.py`, and `ui_robustness.py`
passed again against the latest shared core. Final material-browser, minimum-size
geometry and complete-preview-notes screenshots were visually inspected. GUI
regressions also check image fit/non-overlap, texture-only material identity,
8192×1 thumbnails and warning-state cleanup when the last tab closes.

## Probes that were not defects

- Nested packaged texture references in an assembly remained resolvable after hiding the original source archive; a packaging diagnostic did not imply an actual missing dependency.
- A textured mesh whose faces were all holes loaded without a renderer exception. It had no visible cells, and STL export retained its existing explicit empty-geometry rejection.

## Takeaways and remaining scope

Hashes establish byte integrity, not appearance fidelity. Composition tests must compare inherited UVs, material bindings and sampled values as well as successful publication. Preview failures should degrade to a visible warning for the affected map while leaving other geometry usable. Browser labels should describe authored appearance data, and diagnostics must remain accessible after selection changes.

The minimum-size layout remains dense. A broader responsive-layout pass, a structured application-target editor, a persistent native capture/status panel, and performance testing on very large histories remain worthwhile follow-up work. These were not substituted for the concrete correctness fixes in this pass.

Native Cycles graphs, normal/displacement maps, UDIM sets and arbitrary shader networks remain outside the preview renderer's supported scope. Maps on one rendered surface require compatible UV coordinates and wrapping. Missing UVs use explicitly labeled preview-only box mapping; stored source geometry is unchanged.

The reviews used disposable projects and did not modify demo history or live native documents. Live Blender/Rhino save round trips were not re-certified. This pass does not certify every model, renderer, filesystem failure or application version.
