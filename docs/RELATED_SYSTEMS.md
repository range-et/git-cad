# Existing CAD and cross-application asset management systems

Research date: 2026-11-07. This is a documentation/source comparison, not a hands-on
product certification. The product scope is [the CAD-GIT first release](SPECIFICATION.md).

## 1. Conclusion

Cross-application design data management is an established category. CAD-GIT should
not claim to invent versioned publishing, model exchange, visual comparison, or
asset composition. The strongest workflow comparisons for this project are Prism
for versioned USD assembly, Speckle for CAD/DCC connectors, and FreeCAD History
Workbench for local CAD snapshots and visual changes. AYON is relevant for
publishing/dependency management; OpenAssetIO is relevant to plugin boundaries.

The proposed differentiator is a small fully local Python tool combining immutable
USD save histories, per-document source timelines, deliberately selected main
assemblies, and visual selection/splicing of objects from historical snapshots. Whether that combination
justifies a separate product should be tested against existing systems before
committing to a large implementation.

## 2. Closest systems

### Prism Pipeline

Prism's USD plugin provides a 3D viewport, versioned USD containers and department
layers, and configurable container updates when new layers are published. Its
project settings distinguish push-style master-version references from pull-style
version selection and can record external dependencies on save. This is a close
precedent for source outputs converging into a selected assembly.
[USD documentation](https://prism-pipeline.com/docs/latest/plugins/USD/),
[project settings](https://prism-pipeline.com/docs/latest/general/settings/project/).

Its free core and the USD plugin must not be conflated: the current licensing docs
put the core under LGPL v3 and list USD under Prism Plus. Reuse requires checking
the exact component license and distribution terms.
[Licensing](https://prism-pipeline.com/docs/latest/general/licensing/).

Evaluation: build a small project using independently versioned model/look or
geometry outputs, disable automatic promotion, and select older versions for a
new container. Check how save-triggered snapshots, arbitrary historical object selection,
history retention, and Rhino integration would be implemented. Those exact
requirements are not established merely by its USD publishing documentation.

### Speckle

Speckle supplies cross-application model exchange with Rhino and Blender among its
connectors. Its Blender documentation describes mesh/material transfer into Rhino
and collection-to-layer mapping. The connector repository describes object-based
versioning and model-version loading.
[Blender integration](https://speckle.systems/integrations/blender/),
[connector repository](https://github.com/specklesystems/speckle-blender).

It is a close interoperability reference. Evaluate connector identity, incremental
updates, and representation conversion before writing equivalents. Do not assume
its neutral object model is OpenUSD or that object/model versions provide our desired immutable USD snapshot archive; native files remain current
working documents in the revised CAD-GIT scope. Our folder-only, no-account/runtime-server requirement
needs a separate deployment test; self-hosted infrastructure is not equivalent to
a small local executable. Connector code reuse needs exact licensing/version
review, particularly where legacy and current connector generations differ.

### FreeCAD History Workbench

This workbench describes locally stored CAD history with 3D geometry and tree
comparisons. It is a direct precedent for presenting what changed in a CAD model,
although it is specific to FreeCAD rather than a general multi-app USD core.
[Repository](https://github.com/eblanshey/HistoryWorkbench).

Evaluation: inspect snapshot timing, identity, changed-property presentation,
geometry highlighting, and restore safeguards. Borrow workflow lessons and test
cases; do not infer cross-app merge support from a single-app visual diff.

### AYON

AYON's OpenUSD workflow supports publishing model products and department/scene
layers. Its documented local deployment installs a server stack. This makes it a
useful publishing/dependency architecture reference, while the deployment model
needs comparison with our no-server-setup local requirement.
[OpenUSD workflow](https://help.ayon.app/articles/7468381-ayon-maya-openusd-workflow),
[local deployment](https://help.ayon.app/help/articles/2293963-ayon-server-local-deployment).

Evaluation: examine product/version records, dependency pinning, validation, and
host integration separation. A studio pipeline and a single-user USD snapshot-history
tool need not share the same deployment or UI architecture. Do not assume all
addons or distributed components have the same license or offline availability.

### Traditional PDM and cross-PLM integration

Autodesk Vault documents retention of file versions and dependencies. PROSTEP's
OpenPDM describes integration of PLM information across systems, with on-site and
cloud deployment options. They establish that engineering file history and
cross-system data management are longstanding problems with existing products.
[Vault](https://help.autodesk.com/cloudhelp/Help/ENU/Vault/files/GUID-87D9CA09-9881-4506-9465-0677392BCD7E.htm),
[OpenPDM](https://www.prostep.com/index.php?L=1&id=2028).

Evaluate dependency completeness, revision versus release concepts, and restore
behavior. They are not presumed to be Rust libraries or reusable local USD cores.
No FreeCAD/OpenPDM integration was verified in this research; those products must
not be presented as an established combined solution.

## 3. OpenAssetIO is an integration precedent

OpenAssetIO standardizes communication between content tools and asset managers,
including resolution, publication, and relationships. Its project explicitly says
it is not an asset manager, database, storage system, or pipeline framework.
[Project](https://github.com/OpenAssetIO/OpenAssetIO),
[introduction](https://docs.openassetio.org/OpenAssetIO/).

CAD-GIT should study its host/manager boundary before inventing unnecessary plugin
concepts. A future CAD-GIT manager could expose assets to compatible hosts, but
adopting the API would not supply the history engine. An implementation would
also need an evaluated language/ABI boundary. It is an interoperability option,
not a required v0.1 runtime dependency.

## 4. Reuse and build decision

Separate four decisions:

1. Adopt an existing product if it meets the actual local/history/convergence
   requirements with acceptable setup and licensing.
2. Extend an existing pipeline if a small plugin can supply the missing behavior.
3. Reuse libraries and established protocols for USD, UI, storage indexing, and
   optional MCP, even if the product's domain engine remains new.
4. Build CAD-GIT's own local domain engine only for the remaining requirements:
   save-triggered USD snapshot preservation, explicit source/output lineage,
   dependency-aware object extraction, and deliberate assembly selection.

The current provisional choice is (3) plus a focused version of (4), pending an
executable comparison with the closest products. Python and a local folder are
intentional constraints; they should not be described as proof that an existing
product cannot satisfy the user's modeling workflow.

## 5. Common evaluation task

Use the same small assembly for Prism, Speckle, and our prototype where supported:

- Keep one working file per native app and record save-triggered USD histories
  with their dependent textures/assets.
- Make independent changes in both apps without updating a converged result.
- Select objects from older USD snapshots, including two versions of one shape.
- View the snapshots and deliberately keep, omit, or place both alternatives.
- Publish a selected assembly and derive a reusable output from it.
- Reopen historical USD snapshots and reproduce the selected assembly after
  the native working files and source heads have advanced. Native feature-history
  restoration is not required by the revised product scope.
- Repeat offline, restart after interruption, and inspect retained history.

Record confirmed behavior, required extensions, unsupported features, setup cost,
license boundaries, and measured performance separately. Absence from a product
page is not proof of absence; unsupported conclusions need a test or explicit
upstream documentation. Do not claim CAD-GIT is uniquely capable before this
comparison exists.
