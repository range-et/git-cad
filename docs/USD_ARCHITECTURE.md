# Historical OpenUSD architecture and Rust dependency assessment

Current decision: Python with reference OpenUSD, PySide6/PyVista, and Monad tokens.
The Rust backend and Hydra-first recommendations below are historical research,
not the current implementation contract. See [the final review spec](SPECIFICATION.md).

Research date: 2026-11-07. This records design decisions and a source-level
assessment, not a completed dependency certification. The product contract is
[the CAD-GIT first release](SPECIFICATION.md).

## 1. Decision

CAD-GIT should reuse existing USD implementations, serialization, storage indexing,
UI, and protocol libraries. The custom core is the local revision ledger,
USD source-timeline lineage, arbitrary snapshot selections, assembly recipes,
and deliberate selection of the current main output. Reusing a parser does not supply those
domain semantics.

The leading native Rust USD candidate to evaluate is `mxpv/openusd` with
`openusd-schemas`. Pixar's OpenUSD SDK is the reference comparison engine and
compatibility fallback. Preserve a backend-neutral local worker boundary so the
history format does not depend on a particular crate's types or ABI. Do not select
a library merely because its package is named `openusd` or described as pure Rust.
Production selection remains conditional on the qualification suite below.

## 2. OpenUSD concepts that govern our design

| USD concept | Consequence for CAD-GIT |
| --- | --- |
| Layer | A file/in-memory container of authored scene opinions; not a history commit. |
| Stage | A composed view rooted in layers; our current main exposes one accepted composition. |
| Prim/property paths | A selection is addressed by immutable snapshot ID plus source path/instance; global cross-version identity is optional. |
| Sublayers | Combine opinions at shared paths; strength is deterministic, not a three-way conflict decision. |
| References | Assemble reusable assets beneath scene prims. |
| Payloads | Allow loading selected heavy content. |
| Variants | Represent scene alternatives; CAD-GIT does not use one variant per historical commit. |
| Session layer | Transient application opinions; persistent results must be authored explicitly. |

These concepts are defined in the [OpenUSD glossary](https://openusd.org/release/glossary.html).
The [AOUSD Core Specification](https://aousd.org/usd-core-specification/) formally
specifies the data model, formats, composition, population, and value resolution.
CAD-GIT's snapshot timelines and assembly recipes are an additional application model.

### 2.1 Four separate kinds of time

CAD-GIT MUST distinguish commit history, application save time, selected input
revision, and USD animation time samples. An animated piston moving at frame 10
does not create ten design commits. A later source commit can contain an earlier
animation frame range. Commit selection MUST NOT be encoded by changing the
current animation time. Native feature history is yet another optional provenance
source, not something an exported mesh automatically reveals.

### 2.2 Authored changes and visible changes

The diff engine needs both authored opinions and resolved scene values. An opinion
can change while a stronger layer hides it; a composed value can change because a
referenced asset or variant selection changed. A useful explanation must identify
the contributing layer/revision as well as the visible result. Byte hashes alone
are insufficient for semantic change descriptions.

Converting every stage to one flattened file would simplify viewing while losing
composition structure and authorship detail. Keep original publications plus
their dependency locks, and use flattened scenes only as labelled previews or
exports. The reference [USD toolset](https://openusd.org/release/toolset.html)
includes flattening/conversion, diagnostics, and validation utilities. Its
documentation explicitly notes that passing multiple files to `usdcat` does not
merge them. CAD-GIT must implement its selection and conflict policies itself.

### 2.3 Safe main assembly

Main is an immutable accepted recipe plus the composed USD package produced from
it. The mutable `usd/main.usda` convenience entry points only to the accepted main
commit and MUST NOT reference floating source heads. A recipe pins source snapshot, prim/subtree/instance selection, destination
namespace, placement, dependency versions, and explicit overrides.

Do not reference two complete overlapping app snapshots and trust layer order to
resolve their disagreement. Select contributions by immutable snapshot/path first, then author the result.
The initial subset selects objects/subtrees/instances. CAD-GIT need not discover
that differently named objects across snapshots are the same part or merge their
geometry edits. Dependencies and inherited context still require validated extraction.

Time samples, transform op order/reset stacks, interpolation, purpose, visibility,
primvars, material binding targets, and instance prototypes affect what a user
sees. They require explicit support tests. Unsupported fields remain preserved in
source history and appear in the capability/loss report. A mesh-only preview MUST
not imply support for every USD domain schema or every native feature.

## 3. Backend shortlist and evidence

The following is source/documentation evidence, not our own passing test result.
Repository head changes can differ from published package releases.

| Candidate | Evidence reviewed | Provisional disposition |
| --- | --- | --- |
| [Pixar OpenUSD](https://github.com/PixarAnimationStudios/OpenUSD) | Reference implementation, documented testing guidelines and CI workflow that runs CTest; native SDK build/deployment requirements. | Correctness baseline and fallback; isolate native dependencies. |
| [mxpv/openusd](https://github.com/mxpv/openusd) | Native Rust `openusd`/`openusd-schemas`; roadmap separates release features from development work; CI includes macOS/Linux/Windows Cargo tests and checks. | First Rust-native candidate to qualify. |
| [FloatyMonkey/openusd-rs](https://github.com/FloatyMonkey/openusd-rs) | README describes early API evolution and incomplete feature/compliance work; test instructions require external fixtures and enabling commented tests, with expected failures. | Track as an alternative; not the default reliability choice today. |
| [AndrejOrsula/pxr_rs](https://github.com/AndrejOrsula/pxr_rs) | README explicitly says early development/not production-ready and names OpenUSD 22.11 as its primary target. | Do not adopt as the default production binding without substantial qualification. |
| [luke-titley/usd-rs](https://github.com/luke-titley/usd-rs) | README names USD 23.02 and lists relationships, schemas, edit targets, and variants as remaining work. | Insufficient declared surface for our full workflow without further engineering. |

The [published mxpv crate page](https://docs.rs/crate/openusd/0.8.0) identifies
release 0.8.0. The [roadmap](https://github.com/mxpv/openusd/blob/main/ROADMAP.md)
lists remaining spline, dependency, flattening, and other scope-specific gaps;
features labelled `main` must not be assumed present in 0.8.0. Its
[CI workflow](https://github.com/mxpv/openusd/blob/main/.github/workflows/ci.yml)
runs workspace tests, formatting, linting, and documentation checks. This makes it
a credible evaluation candidate, not proof of full USD compliance or CAD-GIT
round-trip safety.

### 3.1 Reproducible source inspection

These exact repository heads were inspected through source files and tree APIs:

| Repository | Inspected commit |
| --- | --- |
| mxpv/openusd | `cc9e8b0308b12807b121c6dd42de920d46dc7fcb` |
| mxpv/openusd published tag v0.8.0 | `ef823e9a3fd99b711d4109ca1c6db1e9513c2294` (tag resolved; not locally built) |
| FloatyMonkey/openusd-rs | `0372371f678f4bdc73ecab5915368ab734652400` |
| AndrejOrsula/pxr_rs | `f3a05aa8d4dabfa41683dd2d0ea61c34479e44f6` |
| luke-titley/usd-rs | `a7b5c900f7217353dc270d2f13ef09083deeee04` |

The mxpv source tree includes numerous fixtures/integration-test assets. File counts
including fixtures are not test counts and are not a quality metric. We inspected
test/CI definitions; no candidate was compiled or tested locally during this
assessment because this workstation has neither `cargo` nor `rustc` available.
Installing a toolchain and running the selected revision's tests is a required
next engineering task. Do not label these dependencies validated for this product
until that evidence exists.

## 4. Qualification gates before adopting a USD core

1. Pin an exact release/commit, Rust toolchain, feature set, license inventory, and
   lockfile. Keep release and development-head claims separate. Inspect dependency
   advisories, maintenance, and the provenance/license of imported test fixtures.
2. Build on the reference macOS environment; run upstream tests and report passed,
   failed, skipped, ignored, and external-fixture prerequisites separately. A
   missing fixture suite is not a pass. Inspect CI result status, not just YAML.
3. Run AOUSD compliance fixtures appropriate to the selected spec/feature subset
   and compare with the reference SDK. Full-spec conformance is not inferred from
   passing our smaller interchange subset.
4. Run CAD-GIT fixtures covering USDA/USDC reads and writes, relative references,
   sublayers, list operations, payload loading, variants, instance paths, property
   stacks, units, transforms, normals, primvars, and material relationships. Include
   authored and composed-value comparisons, not just successful parsing.
5. Round-trip actual Rhino/Blender exports. Compare resolved hierarchy, identities,
   numeric types, mesh data, relationships, and time samples before/after. Record
   unsupported features; do not normalize them away and call the result lossless.
6. Test missing dependencies, cyclic arcs, invalid indices, huge arrays, truncated
   Crate files, nonfinite values, archive traversal, and worker failure. Bound
   memory and extraction work, and prevent unexpected native/file-format plugin
   loading or remote resource access.
7. Measure cold/warm load, composition, diff, memory, and preview extraction for
   small and multi-part large fixtures. Include cancellation and repeated-worker
   recovery. Never trade away retained native fidelity for viewer frame rate.
8. Produce a checked-in qualification report and backend capability matrix. Select
   the Rust candidate only if it passes the required subset. Otherwise ship the
   reference worker for the affected functionality, with an explicit reason.

An optional fallback must be reproducible: a result pins which backend/version
produced it. Silently switching backends mid-operation can create inconsistent
diffs or composition. Revalidate the entire affected candidate when changing the
backend. All backends feed CAD-GIT's own versioned domain records rather than
serializing third-party Rust objects directly into permanent history.

## 5. Reuse boundaries beyond USD

| Responsibility | Proposed existing component | CAD-GIT retains responsibility for |
| --- | --- | --- |
| CLI parsing | [clap](https://github.com/clap-rs/clap) | Command semantics, protected main, safe defaults. |
| Manifest/protocol encoding | [Serde](https://github.com/serde-rs/serde) and serde_json | Versioned schema, canonical hashing rules, migrations. |
| Local query index | [rusqlite](https://github.com/rusqlite/rusqlite) / SQLite | Durable immutable records, event ordering, rebuild procedure. |
| UI shell | Reference usdview/Qt components preferred; [egui](https://github.com/emilk/egui) remains an optional shell | Timeline, selections, source attribution, recipe controls. |
| USD viewport | Reference OpenUSD imaging/Hydra preferred; [wgpu](https://wgpu.rs/) is a custom-renderer fallback | Source-aware picking, assembly preview, dependency warnings. |
| Optional agent interface | [official Rust MCP SDK](https://github.com/modelcontextprotocol/rust-sdk) | Domain safeguards and parity with local CLI/UI operations. |

These are reuse candidates, not a blanket audit. Before integration, record exact
versions, licenses, enabled features, target support, and relevant test results.
The MCP SDK is optional at runtime; loading the CAD-GIT project cannot require an
agent connection. Git integration libraries are not needed for the core revision
ledger. App-specific modeling APIs remain behind minimal plugins.

## 6. USD histories and deliberate assembly

The product contract now uses one native working path per source and an immutable
USD history per save. Permanent per-save native backups and automatic geometric
reconciliation are outside the first release. This supersedes older native-history
requirements in the original research discussion.

```text
rhino:    R0 → R1 → R2 → R3 → R4 → R5 ...     (USD snapshots)
blender:  B0 → B1 → B2 → B3 → B4 ...          (USD snapshots)

R2:/Engine/Block + R4:/Engine/Cover + B1:/Housing
                         ↓
                 recipe → assembly A1
                         ↓
                   main points to A1
```

Main is a selected result, not a requirement to implement another Git-style graph.
Earlier saved assemblies remain reopenable with their recipes. Source save events
cannot alter a saved recipe, silently advance main, or overwrite another app.

Proposed commands, not yet implemented:

```sh
cad-git init --app rhino --app blender
cad-git begin
cad-git ui
cad-git compose --input R2:/Engine/Block --input R4:/Engine/Cover --input B1:/Housing
cad-git assembly save <draft-id> --name engine-study
cad-git main set <assembly-id>
cad-git export <assembly-id> --output exports/engine.usda
```

Native apps can manually import the resulting USD and continue modeling. The next
save produces another USD snapshot; imported lineage is annotated when known.
The native document itself remains the user's current file, and its full native
historical state is not recoverable from USD alone.

A blank init USD stage and the optional MCP client example are separate files.
The UI must exist in the first release. Prefer an evaluated reference OpenUSD
imaging/Hydra or usdview-derived component for mature viewing/picking over a new
custom renderer. Rust owns the domain core; a native SDK/Qt/Python viewport
companion is acceptable. Parser selection and renderer selection are distinct
qualification tasks. See the [reference viewer documentation](https://openusd.org/release/toolset.html#usdview)
and [StageView source](https://github.com/PixarAnimationStudios/OpenUSD/blob/dev/pxr/usdImaging/usdviewq/stageView.py).

## 7. Decisions still requiring executable evidence

The USD snapshot/assembly scope and persistent lineage model are product decisions.
The exact USD backend, crate versions, GPU picking implementation, packaging,
performance targets, and adapter snapshot APIs require prototypes and tests.
The next useful prototype is: create an empty main, ingest two real app commits,
compose selected parts through the candidate backend, compare the result with the
reference SDK, preview it with a mature viewport, and select it as main without
changing either native working file or any source USD snapshot. This exercises the actual architecture before building a large
plugin or UI framework.
