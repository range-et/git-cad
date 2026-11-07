# Versioned materials and cross-application lineage

Status: proposed design, 2026-11-07. This extends the
[first-release specification](SPECIFICATION.md). It replaces the earlier idea
that all material requirements can be reduced to one PBR parameter subset.

## 1. Material identity is distinct from its representations

A project material is a versioned asset with one or more independent facets:

| Facet | Purpose | Example representations |
| --- | --- | --- |
| Appearance | Rendered/previewed look | Blender/Cycles graph, USD Preview Surface, MaterialX, textures, future Substance asset. |
| Engineering | Physical/constitutive behavior | Density, elastic/plastic/thermal data, provenance, future solver-specific material cards. |
| Assignment | How a selected geometry uses a material | Surface binding, face subset, body/region assignment, mapping coordinates. |

A painted aluminum visual material can be paired with different aluminum grades.
Changing the paint must not change density. A physical grade does not determine
which procedural shader looks appropriate. Catalog entries MAY group related
facets, but neither names nor visual similarity establish physical equivalence.

Every recorded assignment pins material and facet revision IDs. Editing the project library
creates new revisions; already recorded snapshots, assemblies, analyses, and
renders continue referencing their original revisions. No historical result may
silently resolve a floating `latest` material.

### 1.1 Software-independent slots and provider representations

A **material slot** is a stable authored binding identity carried by geometry or
an assembly instance. A **material asset** is a catalog identity independent of
the app that authored any representation. A **representation revision** is one
specific Cycles graph, Rhino preview, OpenFOAM definition, FreeFEM definition,
Ansys card, or portable look. These three identities MUST NOT be conflated with a
native material name or Blender's integer material-slot index.

A slot can refer to separate appearance and engineering assets. It can also have
scoped instance overrides. Copying a selected object into an assembly preserves
source slot lineage while creating a distinct destination occurrence; identical
source slot IDs in two deliberate copies MUST NOT accidentally share overrides.

The connector can create a Rhino material proxy/instance for display and persist
the slot/material references as native metadata. Rhino need not interpret a Cycles
graph or solver card. On export, the adapter MUST record/remap native object or
region bindings into snapshot USD paths and the assignment manifest. A later
CAD-GIT-assisted Blender import resolves the appearance representation, appends
the archived graph, and binds it to the appropriate target. Unsupported native
exporters do not automatically preserve these IDs; adapter/manifest support is a
required contract, not an assumption about plain USD export.

For example, a working binding might follow the latest compatible Blender
representation while keeping the engineering definition pinned. On snapshot,
assembly save, render, or analysis, resolve any `latest` policy to exact revision
IDs and hashes and record the resolver/version. A newer library graph does not
change an old snapshot. Updating an old assembly to latest is a new explicit
derived result. Missing/incompatible provider representations MUST be surfaced,
not substituted by a same-named material.

Bindings target explicit scopes: whole object/instance, surface subset, or
body/analysis region. If a topology edit destroys a region/face assignment, retain
the old binding in history and mark the new assignment unresolved; the slot does
not magically discover where a changed face went. This requires no per-vertex
edit history or automatic geometry matching.

Material commands should expose this bookkeeping, for example (proposed syntax):

```sh
cad-git material bind --slot <slot-id> --appearance <asset-id> --follow latest
cad-git material bind --slot <slot-id> --engineering <asset-id>@<revision-id>
```

Provider-specific definitions can contain different models and parameters. A CFD
or FEM material representation is not automatically derived from a shader or a
generic density value. Preserve its own schema, units, source/version, and task
compatibility; OpenFOAM and FreeFEM are future providers alongside Ansys.

## 2. What USD and MaterialX preserve

`UsdShade` describes material networks and bindings, including renderer-qualified
surface/displacement/volume outputs. This is a place to compose representations,
not a guarantee that every target renderer understands the same node definitions.
[UsdShadeMaterial API](https://openusd.org/release/api/class_usd_shade_material.html).

Blender documents Preview Surface conversion as an approximation of supported
shader graphs and provides MaterialX export with limitations. MaterialX supports
network-based interchange and OpenUSD integration, but feature coverage and import
behavior remain specific to application builds.
[Blender USD manual](https://docs.blender.org/manual/en/5.0/files/import_export/usd.html),
[MaterialX/OpenUSD support](https://materialx.org/ThirdPartySupport).

The three preservation routes MUST remain distinct:

- **Portable graph:** MaterialX/UsdShade for the explicitly tested supported subset.
- **Native fidelity:** retain the authoring application's native material asset
  and use that application/plugin to reconstruct it.
- **Baked appearance:** retain exported texture maps as a derived representation,
  with bake settings and limitations. Baking is not preservation of an editable
  procedural graph.

A result can carry a portable viewport fallback and a native rendering asset at
the same time. Missing graph support must never silently downgrade a promised
native-fidelity result into the fallback.

## 3. Local Blender experiment

A disposable background Blender 5.2.3 LTS process created a material with
`Noise Texture → Color Ramp → Principled BSDF → Material Output`. It exported USD
with material and MaterialX network generation enabled, then imported that USD
with Preview Surface conversion enabled. The imported graph contained only the
Principled and Output nodes; Noise and Color Ramp were absent. This establishes
failure of this particular graph round trip, not the limitations of every possible
MaterialX network or future Blender version.

The same material was written with `bpy.data.libraries.write` to a material-only
`.blend`, then appended back using the native library loader. The compared node
types/names, links, roughness, noise scale, and ramp positions matched. This is
evidence for the native-asset route, not a complete certification of all Cycles
graphs, textures, drivers, or render equivalence.

- [Recorded results](research/blender-material-roundtrip.json)
- [Reproducible background-process probe](../test/materials/probe_blender.py)

The native API's local documentation states that indirectly referenced datablocks
are included by library writing. External images/files and implicit scene context
still require explicit inventory and preservation. The running user Blender scene
was not changed by the experiment.

## 4. Project material library

Recommended layout:

```text
materials/
├── catalog.json                         # Current library index, rebuildable
├── <material-id>/
│   └── revisions/<revision-id>/
│       ├── manifest.json
│       ├── appearance/
│       │   ├── preview.usda
│       │   ├── graph.mtlx                # When supported
│       │   ├── blender/material.blend    # Native graph asset when retained
│       │   └── textures/...
│       ├── engineering/
│       │   ├── properties.json
│       │   └── source-data/...
│       └── thumbnails/...
└── assignments/                         # Optional reusable assignment presets
```

Not every revision needs every representation. Original native assets, derived
portable graphs, physical properties, and render thumbnails are separately typed
payloads with hashes and provenance. Files are immutable after commitment. A
catalog link groups them; it does not assert that shader and physics conversions
are lossless. Referenced dependencies remain part of the recoverable project.

This adds a deliberate exception to the one-native-working-file rule: historical
material-only `.blend` assets can exist in the library while the user's one current
scene `.blend` remains unchanged. It does not require a complete scene copy per
save. A graph whose dependencies force a larger native asset must disclose that
dependency closure/size rather than secretly omit it.

## 5. Geometry from Rhino plus a historical Cycles graph

The required workflow is:

1. On a Blender save, publish the USD snapshot and an immutable revision of each
   newly captured/changed retained material graph. Freeze them from the same
   authoring state; do not pair the old USD snapshot with today's graph.
2. In the assembly UI, select geometry from a Rhino snapshot and select a material
   revision from an older Blender snapshot or the project catalog independently.
3. Record the target prim/region, material revision, binding scope, UV/attribute
   requirements, and supported overrides in the recipe. Validate mappings.
4. Save the USD assembly with portable bindings plus pinned native-material
   references in CAD-GIT metadata/manifest. Preserve the library dependency closure.
5. For a CAD-GIT-assisted Blender import, import geometry, append the exact archived
   Blender material datablock, and bind it according to the recipe. A render task
   records Blender/Cycles versions, graph revision, settings, and output lineage.

A plain standard USD import into an unmodified Blender is only guaranteed the
declared supported portable material route. It will not automatically interpret a
CAD-GIT reference to `material.blend`. Native graph restoration requires the
CAD-GIT adapter or an explicit material-append workflow. A bare USD file copied
without its referenced/native dependencies is not a complete fidelity package.

USD metadata references do not embed a generic Blender graph executor. The bridge
MUST not claim a custom graph automatically runs in Hydra, Rhino, or another DCC.
The UI MUST label preview fidelity separately from intended Cycles fidelity.

Graph preservation also differs from appearance preservation on new geometry.
UV maps, named attributes, object coordinate sources, object-scale assumptions,
displacement bounds, scene objects, drivers, and external files can affect the
result. Missing dependencies must be mapped, included, or explicitly reported.
Applying a texture paint set to a differently UV-mapped mesh is not automatically
valid merely because the material loads successfully.

## 6. Engineering material data

Engineering definitions need quantity units, model names, provenance, revision,
and validity conditions. The initial schema SHOULD accommodate density; optional
elastic, thermal, strength, or nonlinear data remain typed fields/tables with
temperature/direction/dependency information. Unknown quantities are unknown,
not zero or guessed from the material's name.

An engineering assignment targets a body/volume or analysis region. A rendering
assignment targets a surface or face subset; they are not interchangeable.
Density and verified volume can support a mass task. Record which geometry and
units supplied that volume and whether it was native-solid or mesh-derived.
Open or invalid meshes cannot silently produce a trusted volume. PBR reflectance
parameters do not supply density or constitutive behavior.

USD physics can express mass/density in a rigid-body context. That does not make
it a complete FEM material database. Full engineering/solver payloads belong in
the versioned asset package; mirror only a declared supported subset into USD.
[USD physics schema](https://openusd.org/dev/api/usd_physics_page_front.html).

Analysis tasks must pin geometry, meshing, physical material revision, boundary
conditions, loads, solver/version, settings, and result artifacts. Recording those
assets is within CAD-GIT's future role; implementing an FEA/FEM solver is not.
Geometry changes can invalidate analysis region/face assignments. A future solver
adapter must validate or require remapping rather than rely on stable vertex IDs.

## 7. Future provider plugins

| Provider | Authoring/native payload | Derived/interchange payload | Required capability distinction |
| --- | --- | --- | --- |
| Blender/Cycles | Material/node-group `.blend` asset | USD Preview Surface, supported MaterialX, optional baked textures | Preserve native graph versus reconstruct portable graph. |
| Rhino | Supported render material and engineering assignments/custom properties | Exported USD look and typed physical references | Visual PBR is distinct from physical material data. |
| Substance Painter | Versioned source project/assets where requested | Texture sets and supported USD material output | Native paint/layer preservation versus baked outputs. |
| Substance Designer or another procedural provider | Source graph/compiled asset as supported | Texture outputs and supported graph formats | Captured asset versus a runtime/license needed to evaluate it. |
| Ansys/engineering providers | Original exported material card/library | Typed quantities/tables or supported solver interchange | Source/version preservation versus supported property conversion. |

Adobe's format support differs by product; a Painter plugin must not inherit every
format capability of the broader Substance family. Ansys documents Engineering
Data import and notes recognized-data/version compatibility constraints. Adapter
capabilities must name exact application and format versions.
[Adobe format matrix](https://experienceleague.adobe.com/en/docs/substance-3d/general-knowledge/ecosystem/import-and-export-formats),
[Ansys Engineering Data import](https://ansyshelp.ansys.com/public/Views/Secured/corp/v251/en/wb_eda/eda_import_mat.html).

Provider plugins preserve original payloads, identify converted fields, declare
runtime requirements, and record provenance. They must not imply that a product
name guarantees unrestricted redistribution, offline execution, or equivalent
material evaluation in another application.

## 8. Branches, task steps, and the zig-zag timeline

Columns are applications/sources; multiple named branches can exist within each.
A source snapshot records its branch, previous authoring snapshot, and imported
inputs. Relationships cross columns through explicit assembly/import/task events:

```text
Rhino sketch R1 ──→ assembly A1 ──→ Blender organic edit B1
                                          │
Rhino engineering R2 ←── assembly A2 ←─────┘
        │
        └──→ A3 + historical Blender shader M4 ──→ Cycles render artifact
```

This is a lineage graph, not a requirement to merge modeling operations.
Imported inputs and the source branch's previous save are distinct parent roles.
Cross-app lineage must be recorded by the import action or explicitly annotated;
it cannot be deduced reliably from filenames or similar geometry. A material-only
revision can branch/recombine independently of a geometry snapshot.

Default source history remains append-only. A named branch is an independent head
over snapshot records, not another permanently copied native document. Importing
an old USD to continue modeling can start a new branch while native working paths
remain user-managed. Exact restoration of a whole old native document remains
outside the USD-only preservation promise unless separately enabled later.

## 9. First-release commitments and future scope

First release: material assets/revisions, independent material selection and
binding in assembly recipes, portable preview status, a tested Blender-native
material preservation/restore path for a declared supported graph subset, and
basic library browsing in the required UI. Include source sub-branches and
explicit cross-column import lineage; do not build feature/vertex merge tracking.

The engineering namespace, units/provenance model, and catalog linkage should be
designed now. Full engineering library curation, automated mass tasks, FEA/FEM
execution, Substance connectors, and Ansys connectors remain future integrations.
The application can store an opaque versioned engineering card before it can
interpret every field. Supported conversion and mere preservation are separate
capabilities.

The next executable gate is stronger than the current small probe: capture an
older procedural graph with textures/node groups, change the live material, select
new Rhino geometry plus that exact old graph, restore through the adapter, and
render in Cycles. Verify graph/dependency preservation and recorded lineage. Do
not certify the end-to-end feature from the existing four-node experiment alone.
