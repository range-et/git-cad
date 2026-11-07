# Future features and open questions

This document records deferred topics for later review. Entries are not V1
requirements or commitments to a particular implementation.

## Native editability across application round trips

**Status:** Deferred. No change to current V1 scope.

**Question:** How should CAD-GIT preserve or recover native editability when
geometry travels Rhino → Blender → Rhino, or between other applications with
different geometry representations?

The current Rhino capture and return path uses polygon meshes. Returning a mesh
to Rhino does not recover its original NURBS control points or construction
history. The original working `.3dm` retains its native geometry; current durable
USD snapshots do not archive complete native documents.

Options to investigate later:

- Pair selected or every USD snapshot with a versioned native file for exact
  native restoration, weighing storage cost and capture performance.
- Restore unchanged parts from their native source while returning mesh-edited
  parts as meshes, if reliable object identity and change detection are available.
- Offer explicit surface reconstruction or representation conversion, with clear
  limits on fidelity and recovered editability.

Before choosing an approach, establish which workflows need native restoration,
which representations the relevant exporters/importers preserve, and whether
native archives should be automatic, optional, or milestone-based.

For V1, continue with USD snapshot history, lineage, geometry selection and
assembly, visualization, and export. Native NURBS restoration is not a release
gate.

## Follow-ups from the adversarial reviews

These are usability/scaling improvements, not unresolved silent-data-loss fixes.
See [review findings and fixes](REVIEWS_AND_HARDENING.md) for completed work.

- A persistent per-application capture panel showing binding, capture branch,
  latest snapshot, queued/failed events, retry and Stop controls.
- A guided branch-from-history action that distinguishes assigning future saves
  to a branch from opening historical contents in a new native working file.
- Stable native document IDs alongside application/branch lanes, so independent
  files can have separate streams while retaining cross-tool lineage.
- Mark or refresh assembly previews when their draft recipe changes.
- Cache the history index and virtualize graph rendering for very large projects.
- Display timestamps in the user's timezone and expand screen-reader support.
- Show material-override fidelity explicitly: native renderer graph restoration
  and manager inspection shading are different capabilities.
- Stage/cache cleanup policies and explicit recovery tooling for failed captures,
  avoiding automatic deletion of data needed for diagnosis.
