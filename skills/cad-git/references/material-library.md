# Portbook: materials, images, graphs and specifications

Use this alongside the geometry onboarding guide. The result is a usable project
catalog with honest provenance and pinned revisions, not a collection of guessed
material names or a copy of the generated demo. Commands below use CADGIT_BIN and
CADGIT_PROJECT established in onboarding.md; repeat them in a fresh shell.

## Classify the existing folder

Use the read-only inspector, then map the chosen inputs into these roles:

| Input | Porting role |
| --- | --- |
| Native working `.3dm` / scene `.blend` | Geometry baseline through its chosen application. |
| Shader-library `.blend`, `.mtlx`, `.sbsar` | Independent shader asset; archive support is not proof of renderer compatibility. |
| PNG/JPEG/TIFF/EXR/HDR | Independent image asset; confirm map role and color space rather than infer physical properties. |
| PDF/text/CSV/JSON material evidence | Specification/document asset; do not interpret arbitrary JSON as a CAD-GIT definition. |
| Existing physical data / authored appearance | Explicit logical material definition with units, sources and pinned asset refs. |
| ZIP download | Keep opaque or have the user extract separately; V1 does not extract archives. |

One material can use many images; one image can be reused by many materials. Do
not identify continuing assets just by matching filenames or content hashes.
Retain original folder organization and linked dependencies. A pre-existing
`library/` or `materials/` can force a new CAD-GIT child root, not a move/deletion.
The inspector excludes recognized generated libraries/history from new candidates.

Before writing, identify which files are new assets versus new revisions of known
assets. Record ambiguous classifications as choices still needed. Independent
geometry or asset work can continue while an unavailable native application waits.

## Register independent assets

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library list
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library import \
  "/absolute/original/base-color.png" --kind image --label "Polymer base color"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library import \
  "/absolute/original/grade-datasheet.pdf" --kind document --label "Grade datasheet"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library import \
  "/absolute/original/shader.blend" --kind shader --label "Blender appearance"
```

Capture the returned stable asset_id and immutable revision id for each file.
Supply known `--provider`, `--source-url`, `--license-name` and `--note` as applicable.
Missing license information remains unknown; “free” does not establish rights to
redistribute. Preserve original source names and versions, manufacturer/test context
and license evidence. Do not download, authenticate to a provider, or upload assets
to an AI service merely to initialize a local library.

Poliigon V1 integration is **Browse Poliigon** in the system browser followed by
import of the user's locally downloaded files. It is not an authenticated catalog
API, scraper or automatic download service. Record the specific source page and
user-supplied license information. Keep provider assets local unless permitted.

## Create the logical material

Create a new, unused working JSON file containing a material definition. Use
actual returned revision IDs instead of the example placeholders:

```json
{
  "physical": {
    "properties": {
      "density": {
        "value": null,
        "unit": "kg/m3",
        "status": "unspecified",
        "source": "No grade-specific value supplied"
      }
    }
  },
  "appearance": {
    "preview": {"base_color": [0.6, 0.6, 0.6], "roughness": 0.4, "metallic": 0},
    "native_graph": "SHADER_REVISION_ID",
    "material_name": "Exact Blender material datablock name if multiple exist",
    "maps": {
      "base_color": {"revision_id": "IMAGE_REVISION_ID", "color_space": "sRGB", "uv_set": "st"}
    },
    "graph_images": {"Exact original Blender image name": "IMAGE_REVISION_ID"}
  },
  "documents": [{"revision_id": "DOCUMENT_REVISION_ID", "note": "Grade-specific evidence"}]
}
```

Remove sections/references that are not available. A physical-only material with no
appearance is valid. Omit `material_name` when the native library has exactly one
material and that is the intended graph. `graph_images` maps original image
**datablock names**, not guessed filenames; supply these when a native graph uses
external images. Packed native graph images do not need a guessed external map.
Image imports preserve bytes, not application-specific color interpretation.

Replace null physics values only with sourced data, including units, status and
relevant grade/process/temperature/orientation conditions. Do not use 0 for unknown
values, copy illustrative demo constants as real PLA data, convert units silently,
or claim suitability for an FEA/CFD solver. Unknown future fields must survive edits.
The UI **New material / New revision** editor provides the same fields as a table.

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library material "PLA — selected grade" \
  --definition "/absolute/path/new-material-definition.json"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library verify MATERIAL_REVISION_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library show MATERIAL_REVISION_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library used-by IMAGE_REVISION_ID
```

## Revision, derivative and recombination semantics

New image bytes become a new revision only when the user identifies them as a
continuation of that asset. The expected revision prevents an outdated edit from
silently replacing a newer head:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library import \
  "/absolute/path/edited-color.png" --kind image \
  --asset-id ASSET_ID --from CURRENT_IMAGE_REVISION_ID --note "Edited externally"
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library history ASSET_ID
```

Existing materials still point to the earlier image. Revise the material explicitly
to adopt the new image, using its stable asset_id and `--from CURRENT_MATERIAL_REV`
with a full definition cloned from the selected revision. If the expected head is
stale, reload or derive a new identity; do not bypass the conflict check. Use
`library import ... --parent INPUT_REVISION_ID` without asset-id to create a new
asset linked to derivative inputs. This records provenance; it does not claim the
manager edited the pixels. Same-identity named branch management is not in V1.

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" library recombine "PLA + chosen finish" \
  --physical-from PHYSICAL_MATERIAL_REV --appearance-from APPEARANCE_MATERIAL_REV
```

This copies the two chosen facets and records both donors. It does not average
engineering numbers or merge shader nodes. Original revisions remain unchanged.

## Assign and verify the complete workflow

In the UI, **Materials & Assets → select exact revision → Use for new pieces**
returns to Geometry and changes the assignment for subsequently added pieces.
Already-added pieces remain pinned. The CLI can assign one chosen material to all
pieces in a composition:

```sh
"$CADGIT_BIN" -p "$CADGIT_PROJECT" compose \
  --input "SNAPSHOT_ID:/Actual/PrimPath" --library-material MATERIAL_REVISION_ID
"$CADGIT_BIN" -p "$CADGIT_PROJECT" verify ASSEMBLY_ID
```

Inspect actual prim paths first. Use the UI or MCP selections with
`library_material_revision` for per-piece choices. The older `material_revision`
field still identifies a captured native shader, not a logical PLA definition.

Verification checks hashes and dependencies. It does not certify a native shader,
engineering values, UVs or a render result. Portable USD map projection supports
base_color, roughness, metallic and opacity with raw/sRGB/auto color spaces;
unsupported map roles/color spaces remain recorded and need a compatible native
representation or explicit conversion. The inspection viewport uses a basic
preview; it does not evaluate Cycles. Shader formats other than a supported
`.blend` graph can be archived without claiming Blender restoration.

Native captures keep the logical material association and separately capture the
actual native appearance. Edited/cleared Blender appearance is not replaced by an
older library graph on return. Approve such an appearance as a new material revision
explicitly if it should become the reusable library definition. Ambiguous native
material/image identity must be reported, not guessed.

Handoff includes stable asset IDs, exact revisions, pinned dependency roles,
source/license status, unknown physics, and which native graphs/renderers were
actually tested. Do not call the folder fully ported if only geometry was captured
while requested material data, images or specifications remain unregistered.
