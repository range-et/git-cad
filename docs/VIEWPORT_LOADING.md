# Viewport loading and responsiveness

The November 8, 2026 investigation found that USD verification and extraction
already ran in Qt workers. The blocking callback then packed textures, constructed
VTK geometry, generated normals/split sharp edges, added all actors, and requested
renders while adding each object. Coroutines alone would not move this CPU work
off the GUI thread.

CPU preparation now runs in a bounded two-worker scene pool. Workers own their
datasets until completion and never touch widgets, renderers or OpenGL objects.
Source geometry remains unchanged. The GUI receives evaluated datasets, installs
actors with per-object rendering/camera resets disabled, and yields between
roughly 8 ms batches. An individual actor operation can exceed this budget.
The tab displays an object counter and becomes usable only after completion.
Bounds are reduced in the worker instead of concatenating all scene points on
the GUI thread. Both saved scenes and assembly drafts use this path.

Closing a tab stops upload timers and discards late results. Queued loads check
cancellation before reading; active preparation checks between objects. An active
USD read, integrity hash or single VTK filter is allowed to finish safely rather
than being forcibly interrupted. Other save/export jobs use the existing pool.

The final GPU upload/render remains synchronous, as do subsequent viewport frames.
This change does not promise an upper bound for enormous individual meshes, GPU
memory exhaustion or expensive transparency/ambient occlusion. Level-of-detail
rendering and out-of-core scene streaming remain possible future improvements.

Validation: `tests/integration/viewport_responsiveness.py` loads an actual USD with
401 meshes and 249,800 triangles, asserts CPU preparation occurs off the GUI thread,
checks that actor insertion suppresses repeated renders, and observes UI heartbeats
between batches. On the development Mac it completed in 1.63 seconds with 78 UI
heartbeats and a largest heartbeat gap of 0.326 seconds. These are observations,
not portable performance guarantees. The test also exercises all four display
modes, checks archive integrity, and closes a tab during pending upload.
Existing geometry, texture-pixel and failure/retry UI checks remain applicable.

A separate read-only viewport probe of the user's 72 MB archived scene loaded
1,149 objects with 1,709,173 source points in 6.55 seconds (1.16 seconds reading,
3.57 seconds through CPU preparation). It observed 587 UI heartbeats with a largest
gap of 0.041 seconds. That probe used a 900×650 shaded viewport; it does not predict
full-resolution rendered-mode frame times or verify every material visually.

References: [Qt GUI thread rules](https://doc.qt.io/qt-6/threads-qobject.html),
[PyVista actor/render options](https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.add_mesh).
