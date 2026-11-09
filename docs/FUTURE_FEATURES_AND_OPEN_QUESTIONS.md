# Future features and open questions

This design note preserves the reasoning behind deferred native-editability work.
As of 2026-11-09, [issues.md](../issues.md) is the authoritative open-work ledger;
[features.md](../features.md) records implemented capabilities. This note is not
a second backlog or a commitment to a particular implementation. See issue #7.

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

Open follow-ups now live in [issues.md](../issues.md): capture and branching (#5),
scene/history scaling (#6), material fidelity (#8), accessibility (#9), and
adapters/recovery (#10). Completed fixes remain in
[review findings and fixes](REVIEWS_AND_HARDENING.md).
