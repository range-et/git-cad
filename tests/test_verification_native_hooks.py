"""Bundled hook control/data contracts using isolated fake native APIs, not fidelity."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_history import box
from test_native_adapter_recovery import attach_fake_blender, blender_runtime

from cadgit.store import Project


class NodeTree:
    def __init__(self, nodes):
        self.nodes = nodes


class Material:
    def __init__(self, name, tree=None):
        self.name = name
        self.node_tree = tree


@pytest.mark.parametrize("custom_properties", [False, True])
def test_blender_hook_publishes_complete_metadata_and_nested_image_map(
    tmp_path, monkeypatch, custom_properties
):
    project = Project.init(tmp_path / "project")
    bpy = blender_runtime(monkeypatch)
    image = tmp_path / "image.png"
    image.write_bytes(b"opaque external image fixture")
    nested = NodeTree(
        [
            SimpleNamespace(
                image=SimpleNamespace(
                    filepath=str(image), name="Texture", packed_file=None
                )
            )
        ]
    )
    nested.nodes.append(SimpleNamespace(node_tree=nested))
    tree = NodeTree(
        [
            SimpleNamespace(node_tree=nested),
            SimpleNamespace(
                image=SimpleNamespace(
                    filepath=str(tmp_path / "missing.png"),
                    name="Missing",
                    packed_file=None,
                )
            ),
            SimpleNamespace(
                image=SimpleNamespace(
                    filepath=str(tmp_path / "packed.png"),
                    name="Packed",
                    packed_file=object(),
                )
            ),
        ]
    )
    material = Material("Valid", tree)
    broken = Material("Broken")
    plain = Material("Plain")
    bpy.context = SimpleNamespace(
        scene=SimpleNamespace(
            objects=[
                SimpleNamespace(
                    type="MESH",
                    data=SimpleNamespace(materials=[material, broken, plain, None]),
                ),
                SimpleNamespace(type="LIGHT"),
            ]
        )
    )
    calls = []

    class Export:
        def get_rna_type(self):
            return SimpleNamespace(
                properties={"export_custom_properties"} if custom_properties else set()
            )

        def __call__(self, **options):
            calls.append(options)
            box(Path(options["filepath"]))
            return {"FINISHED"}

    bpy.ops = SimpleNamespace(wm=SimpleNamespace(usd_export=Export()))

    def write(path, materials, **options):
        assert options == {"fake_user": True, "path_remap": "ABSOLUTE"}
        if next(iter(materials)).name == "Broken":
            raise OSError("Native graph unavailable")
        Path(path).write_bytes(b"opaque shader fixture")

    working = tmp_path / "working.blend"
    bpy.data = SimpleNamespace(
        filepath=str(working), libraries=SimpleNamespace(write=write)
    )
    bpy.path = SimpleNamespace(abspath=lambda path: path)
    bpy.app.version_string = "Fake API test runtime"
    namespace = attach_fake_blender(project)
    namespace["cadgit_capture"]("tool_snapshot")
    namespace["cadgit_save_post"](None)
    directories = sorted(
        (project.root / ".cadgit/inbox").iterdir(),
        key=lambda path: json.loads((path / "ready.json").read_text())["metadata"][
            "sequence"
        ],
    )
    assert len(directories) == 2
    for index, directory in enumerate(directories):
        ready = json.loads((directory / "ready.json").read_text())
        assert ready["source"] == "blender" and ready["branch"] == "main"
        assert ready["label"] == "working" and ready["file"] == "scene.usda"
        assert ready["metadata"]["sequence"] == index + 1
        assert ready["metadata"]["native_state_saved"] is bool(index)
        assert ready["metadata"]["trigger"] == (
            "user_save" if index else "tool_snapshot"
        )
        assert ready["metadata"]["warnings"] == [
            "Native material capture failed: Broken: Native graph unavailable",
            "Unavailable image: Missing",
        ]
        mapping = json.loads((directory / "materials.json").read_text())
        assert {entry["name"] for entry in mapping.values()} == {"Plain", "Valid"}
        assert next(entry for entry in mapping.values() if entry["name"] == "Valid")[
            "images"
        ] == {"Texture": str(image)}
        assert (
            not (directory / "ready.tmp").exists()
            and not (directory / "failed.json").exists()
        )
    assert all(
        ("export_custom_properties" in call) is custom_properties for call in calls
    )
    assert json.loads((project.root / ".cadgit/sequence_blender.json").read_text()) == {
        "sequence": 2
    }


def test_blender_cancelled_export_leaves_failure_marker_and_no_ready_capture(
    tmp_path, monkeypatch
):
    project = Project.init(tmp_path / "project")
    bpy = blender_runtime(monkeypatch)

    class Export:
        def get_rna_type(self):
            return SimpleNamespace(properties=set())

        def __call__(self, **options):
            return {"CANCELLED"}

    bpy.ops = SimpleNamespace(wm=SimpleNamespace(usd_export=Export()))
    namespace = attach_fake_blender(project)
    namespace["cadgit_capture"]()
    directory = next((project.root / ".cadgit/inbox").iterdir())
    failure = json.loads((directory / "failed.json").read_text())
    assert (
        failure["source"] == "blender"
        and "USD export did not finish" in failure["error"]
    )
    assert "RuntimeError" in failure["traceback"]
    assert not (directory / "ready.json").exists()
    assert not project.records()


class RhinoMesh:
    def __init__(self, vertices=(), faces=()):
        self.Vertices = [SimpleNamespace(X=x, Y=y, Z=z) for x, y, z in vertices]
        self.Faces = [
            SimpleNamespace(A=f[0], B=f[1], C=f[2], D=f[-1], IsTriangle=len(f) == 3)
            for f in faces
        ]

    def Append(self, part):
        offset = len(self.Vertices)
        self.Vertices.extend(part.Vertices)
        self.Faces.extend(
            SimpleNamespace(
                A=f.A + offset,
                B=f.B + offset,
                C=f.C + offset,
                D=f.D + offset,
                IsTriangle=f.IsTriangle,
            )
            for f in part.Faces
        )

    @staticmethod
    def CreateFromBrep(brep, parameters):
        return brep.parts


class RhinoBrep:
    def __init__(self, parts):
        self.parts = parts


def rhino_export_runtime(monkeypatch):
    from test_native_adapter_recovery import rhino_runtime

    rhino, context, opened, disposed = rhino_runtime(monkeypatch)
    rhino.Geometry = SimpleNamespace(
        Mesh=RhinoMesh,
        Brep=RhinoBrep,
        MeshingParameters=SimpleNamespace(Default=object()),
    )
    rhino.UnitSystem = SimpleNamespace(Meters="meters")
    rhino.RhinoMath = SimpleNamespace(UnitScale=lambda source, target: 0.001)
    return rhino, context, opened, disposed


def test_rhino_export_serializes_triangle_quad_names_and_material_pins(
    tmp_path, monkeypatch
):
    from pxr import Usd, UsdGeom
    from test_native_adapter_recovery import attach_fake_rhino

    project = Project.init(tmp_path / "project")
    rhino_export_runtime(monkeypatch)
    namespace = attach_fake_rhino(project.root)
    triangle = RhinoMesh([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    quad = RhinoMesh([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2, 3)])
    strings = {
        "cadgit_material_revision": "mat_example",
        "cadgit_library_material_revision": "assetrev_example",
    }
    attrs = SimpleNamespace(
        Name='Bracket "A"', GetUserString=lambda name: strings.get(name)
    )
    plain = SimpleNamespace(Name=None, GetUserString=lambda name: None)
    objects = [
        SimpleNamespace(IsDeleted=True),
        SimpleNamespace(
            IsDeleted=False, Id="mesh-id", Geometry=triangle, Attributes=attrs
        ),
        SimpleNamespace(
            IsDeleted=False, Id="brep-id", Geometry=RhinoBrep([quad]), Attributes=plain
        ),
        SimpleNamespace(
            IsDeleted=False,
            Id="convert-id",
            Geometry=SimpleNamespace(ToBrep=lambda: RhinoBrep([triangle])),
            Attributes=plain,
        ),
    ]
    directory = project.root / ".cadgit/inbox/export"
    directory.mkdir()
    (directory / "pending.json").write_text("{}")
    namespace["cadgit_export"](
        SimpleNamespace(ModelUnitSystem="millimeters", Objects=objects),
        directory,
        {"branch": "frozen", "document_name": "Fixture"},
    )
    ready = json.loads((directory / "ready.json").read_text())
    assert ready["branch"] == "frozen" and ready["label"] == "Fixture"
    assert "branch" not in ready["metadata"]
    assert not (directory / "pending.json").exists()
    stage = Usd.Stage.Open(str(directory / "scene.usda"))
    assert (
        UsdGeom.GetStageMetersPerUnit(stage) == 0.001
        and UsdGeom.GetStageUpAxis(stage) == "Z"
    )
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath("/Rhino/Object_mesh_id"))
    assert list(mesh.GetFaceVertexCountsAttr().Get()) == [3]
    assert list(mesh.GetFaceVertexIndicesAttr().Get()) == [0, 1, 2]
    assert mesh.GetPrim().GetAttribute("cadgit:objectName").Get() == 'Bracket "A"'
    assert (
        mesh.GetPrim().GetAttribute("userProperties:cadgit:material_revision").Get()
        == "mat_example"
    )
    assert (
        mesh.GetPrim()
        .GetAttribute("userProperties:cadgit:library_material_revision")
        .Get()
        == "assetrev_example"
    )
    assert (
        mesh.GetPrim()
        .GetAttribute("userProperties:cadgit:library_appearance_source")
        .Get()
        == "library"
    )
    assert list(
        UsdGeom.Mesh(stage.GetPrimAtPath("/Rhino/Object_brep_id"))
        .GetFaceVertexCountsAttr()
        .Get()
    ) == [4]
    assert stage.GetPrimAtPath("/Rhino/Object_convert_id")


def test_rhino_unsupported_geometry_rejects_partial_capture(tmp_path, monkeypatch):
    from test_native_adapter_recovery import attach_fake_rhino

    project = Project.init(tmp_path / "project")
    rhino_export_runtime(monkeypatch)
    namespace = attach_fake_rhino(project.root)
    directory = project.root / ".cadgit/inbox/export"
    directory.mkdir()
    obj = SimpleNamespace(IsDeleted=False, Id="unsupported", Geometry=object())
    namespace["cadgit_export"](
        SimpleNamespace(ModelUnitSystem="millimeters", Objects=[obj]), directory, {}
    )
    failure = json.loads((directory / "failed.json").read_text())
    assert "unsupported Rhino geometry unsupported" in failure["error"]
    assert (
        not (directory / "ready.json").exists()
        and not (directory / "scene.usda").exists()
    )


class NativeAttributes:
    def __init__(self, name="", source="parent", index=0):
        self.Name = name
        self.MaterialSource = source
        self.MaterialIndex = index
        self.strings = {}

    def Duplicate(self):
        import copy

        return copy.deepcopy(self)

    def SetUserString(self, key, value):
        self.strings[key] = value


class NativeGeometry:
    def __init__(self):
        self.transforms = []

    def Duplicate(self):
        return NativeGeometry()

    def Transform(self, transform):
        self.transforms.append(transform)


class NativeTransform:
    def __init__(self, value):
        self.value = value

    def __mul__(self, other):
        return NativeTransform(self.value + "/" + other.value)


class NativeInstance:
    def __init__(self, children):
        self.Attributes = NativeAttributes("Outer", "object", 7)
        self.InstanceXform = NativeTransform("placed")
        self.InstanceDefinition = SimpleNamespace(
            Name="Definition", GetObjects=lambda: children
        )
        self.IsDeleted = False
        self.IsInstanceDefinitionGeometry = False


@pytest.mark.parametrize("write_success", [False, True])
def test_rhino_save_freezes_instance_geometry_and_releases_native_resources(
    tmp_path, monkeypatch, write_success
):
    import sys

    from test_native_adapter_recovery import attach_fake_rhino

    project = Project.init(tmp_path / "project")
    rhino, _, _, _ = rhino_export_runtime(monkeypatch)
    rhino.RhinoApp.Version = "Fake API runtime"
    snapshots = []

    class Frozen:
        def __init__(self):
            self.Settings = SimpleNamespace()
            self.layers = []
            self.materials = []
            self.objects = []
            self.disposed = False
            self.Layers = SimpleNamespace(Add=self.layers.append)
            self.Materials = SimpleNamespace(Add=self.materials.append)
            self.Objects = SimpleNamespace(
                Add=lambda geometry, attributes: self.objects.append(
                    (geometry, attributes)
                )
            )
            snapshots.append(self)

        def Write(self, path, version):
            assert version == 8
            if write_success:
                Path(path).write_bytes(b"opaque frozen native fixture")
            return write_success

        def Dispose(self):
            self.disposed = True

    rhino.FileIO = SimpleNamespace(File3dm=Frozen)
    rhino.Geometry.Transform = SimpleNamespace(Identity=NativeTransform("identity"))
    rhino.DocObjects = SimpleNamespace(
        InstanceObject=NativeInstance,
        ObjectMaterialSource=SimpleNamespace(MaterialFromParent="parent"),
    )
    monkeypatch.setitem(
        sys.modules,
        "System",
        SimpleNamespace(Guid=SimpleNamespace(NewGuid=lambda: "new-object-id")),
    )
    child = SimpleNamespace(
        Attributes=NativeAttributes("Child"), Geometry=NativeGeometry(), Id="child-id"
    )
    ordinary = SimpleNamespace(
        IsDeleted=False,
        IsInstanceDefinitionGeometry=False,
        Attributes=NativeAttributes("Ordinary"),
        Geometry=NativeGeometry(),
        Id="ordinary",
    )
    objects = [
        SimpleNamespace(IsDeleted=True),
        SimpleNamespace(IsDeleted=False, IsInstanceDefinitionGeometry=True),
        NativeInstance([child]),
        ordinary,
    ]
    doc = SimpleNamespace(
        Path=str(tmp_path / "working.3dm"),
        Name="Working",
        ModelUnitSystem="millimeters",
        ModelAbsoluteTolerance=0.01,
        Layers=["Layer"],
        Materials=["Material"],
        Objects=objects,
        RuntimeSerialNumber=123,
    )
    namespace = attach_fake_rhino(project.root)
    namespace["cadgit_capture"]("user_save", doc)
    assert (
        snapshots[0].disposed
        and snapshots[0].layers == ["Layer"]
        and snapshots[0].materials == ["Material"]
    )
    assert snapshots[0].Settings.ModelAbsoluteTolerance == 0.01
    geometry, attributes = snapshots[0].objects[0]
    assert geometry.transforms[0].value == "identity/placed"
    assert attributes.Name == "Outer__Child" and attributes.ObjectId == "new-object-id"
    assert attributes.MaterialSource == "object" and attributes.MaterialIndex == 7
    assert attributes.strings == {"cadgit_instance_source": "child-id"}
    assert child.Attributes.Name == "Child" and not child.Geometry.transforms
    directory = next((project.root / ".cadgit/inbox").iterdir())
    if write_success:
        assert len(namespace["_cadgit_queue"]) == 1
        pending = json.loads((directory / "pending.json").read_text())
        assert (
            pending["branch"] == "main"
            and pending["sequence"] == 1
            and pending["native_state_saved"]
        )
        assert (
            directory / "native_capture.3dm"
        ).read_bytes() == b"opaque frozen native fixture"
        assert not (directory / "ready.json").exists()
    else:
        assert not namespace["_cadgit_queue"]
        assert (
            "In-memory native geometry snapshot failed"
            in json.loads((directory / "failed.json").read_text())["error"]
        )
        assert not (directory / "pending.json").exists()


def test_rhino_idle_failure_releases_busy_state_and_retains_native_input(
    tmp_path, monkeypatch
):
    from test_native_adapter_recovery import attach_fake_rhino, pending

    project = Project.init(tmp_path / "project")
    rhino, _, _, _ = rhino_export_runtime(monkeypatch)
    directory = pending(project.root, "capture", 1)
    namespace = attach_fake_rhino(project.root)
    rhino.RhinoDoc.OpenHeadless = lambda path: None
    namespace["cadgit_idle"](None, None)
    assert not namespace["_cadgit_state"]["busy"] and not namespace["_cadgit_queue"]
    assert (directory / "native_capture.3dm").exists()
    assert (
        "Cannot reopen exact native save"
        in json.loads((directory / "failed.json").read_text())["error"]
    )
    namespace["cadgit_idle"](None, None)
