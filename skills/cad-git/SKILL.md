---
name: cad-git
description: Set up and operate CAD-GIT local USD history projects, including onboarding geometry, materials, images, shaders and specifications into immutable project history while preserving existing files and pinned asset lineage.
---

# CAD-GIT

Use CAD-GIT to manage local USD snapshot history, inspect saved scenes, select
geometry across versions, and compose new assemblies. This skill works with any
agent that can read Markdown and run local commands; MCP is optional. Follow the
implemented tool contract, not unimplemented features in a design specification.

## Choose the workflow

- **Onboard an existing folder:** read [references/onboarding.md](references/onboarding.md).
  Inventory the files, choose a safe project root, initialize, record real
  geometry baselines and asset/material revisions, verify them, and explain how to keep working.
- **Port or maintain materials/images/specs:** read [references/material-library.md](references/material-library.md).
  Classify files by role, archive independently, create sourced material definitions,
  pin dependencies and verify renderer support separately from byte integrity.
- **Operate an initialized project:** read [references/tool-contract.md](references/tool-contract.md)
  for commands, data meanings, adapter behavior, and supported limitations.

Use the CLI as the common interface. Resolve the installed `cad-git` executable,
or use `<tool-checkout>/.venv/bin/cad-git`. Shell aliases from an earlier chat are
not a portable installation. If dependencies are missing, use Python 3.12 or 3.13
and `uv sync --project <tool-checkout> --extra mcp`; the tool and user's design
project are separate folders. Consult the installed CLI's `--help` if an option
differs from these examples.

## Essential behavior

- Each tracked native save exports a **whole-scene USD snapshot**. Native files
  continue behaving normally; previous full native documents are not archived.
- Rhino and Blender have independent source histories and capture branches. Main
  is a deliberately selected saved assembly, not an automatically synchronized
  latest scene. A source-branch change does not restore native document contents.
- Assemble by choosing actual prim/subtree paths from specific snapshot IDs.
  Files commonly contain many parts; do not require a separate file per part.
- Native continuation creates a **new native working file** with a lineage
  sidecar. Keep that sidecar with the file. Importing a USD manually does not
  guarantee that its ancestry will be recognized by a later native save.
- A live application binding belongs to one CAD-GIT project at a time. `begin`
  attaches hooks and starts ingestion; inspect its per-app result. A running
  service alone does not prove that either application is connected or captured.
- Record only the history actually captured. Existing files become imported
  baselines; do not fabricate earlier saves, dates, app provenance, or lineage.

## Materials and assets are first-class history

The UI has separate **Geometry** and **Materials & Assets** workspaces. A logical
material combines physical properties, portable appearance, native graphs, maps
and supporting documents. Each image, graph and document is an independently
versioned asset. Stable asset IDs identify continuing items; exact revision IDs
pin dependencies. Never replace a pinned image with a newer head implicitly.

A `.blend` can be a scene or a shader library: classify its intended role before
capturing/importing it. Missing physics values remain unspecified, not inferred
from “PLA” or a texture. Same-asset revisions require the expected current revision;
stale edits fail. Derive creates a new identity linked to selected inputs, and
recombine explicitly selects physical/appearance donors rather than averaging data.

## Preserve the user's project

Leave existing native files, textures and linked assets in place by default.
`source/` is a suggested location, not a requirement to move files. Use a dedicated
project subfolder when initialization conflicts with existing folder names. Do
not delete a conflicting folder, overwrite a native file, or transplant sample
records to make onboarding appear successful.

Use CLI operations for ingestion, composition, main selection and export. Treat
committed snapshots, material revisions and artifact manifests as immutable. Keep
unknown optional configuration fields intact. Do not erase failed inbox captures
or damaged manifests to clear an error; retain the evidence and report the path.
The data format is additive, and unsupported required semantics need a compatible
reader rather than an improvised in-place migration.

## Verify the result and report it

Return the project root, executable used, original native-file locations, chosen
app bindings/capture branches, verified baseline IDs, and any assembly/output IDs. Include material/asset identities and revision IDs,
physical-data sources/unknowns, pinned image/document/graph dependencies, and which
native representations were actually validated.
Differentiate working commands and verified captures from unavailable adapters or
steps awaiting an application. Describe how to start the UI, reconnect save hooks,
and stop this project's watcher. Avoid claiming full native round-trip editability,
shader interchange or printability certification.
