from __future__ import annotations
import math, os, shutil, struct
from pathlib import Path
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade
from .store import CadgitError, atomic_json, now, uid,publish_file
from .models import Assembly, Selection
from .compatibility import check_compatibility


def open_stage(path):
    stage = Usd.Stage.Open(str(path))
    if not stage: raise CadgitError(f"Cannot open USD stage: {path}")
    return stage


def basis(stage):
    scale = UsdGeom.GetStageMetersPerUnit(stage)
    if not math.isfinite(scale) or scale <= 0: raise CadgitError("Invalid USD unit scale")
    # Gf uses row vectors. Y-up -> Z-up: (x,y,z) -> (x,-z,y).
    m = Gf.Matrix4d(1)
    if UsdGeom.GetStageUpAxis(stage) == "Y":
        m = Gf.Matrix4d(1,0,0,0, 0,0,1,0, 0,-1,0,0, 0,0,0,1)
    return m * Gf.Matrix4d().SetScale(scale)


def meshes(path, selection=None, time=0.0):
    stage = open_stage(path)
    selected = stage.GetPrimAtPath(selection) if selection else stage.GetPseudoRoot()
    if not selected: raise CadgitError(f"Prim not found: {selection}")
    cache = UsdGeom.XformCache(Usd.TimeCode(time)); conversion = basis(stage)
    output = []
    for prim in Usd.PrimRange(selected, Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh): continue
        imageable = UsdGeom.Imageable(prim)
        if imageable.ComputeVisibility(Usd.TimeCode(time)) == "invisible": continue
        mesh = UsdGeom.Mesh(prim)
        pts = np.asarray(mesh.GetPointsAttr().Get(Usd.TimeCode(time)), dtype=np.float64)
        counts = np.asarray(mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode(time)), dtype=np.int64)
        indices = np.asarray(mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode(time)), dtype=np.int64)
        if pts.ndim != 2 or pts.shape[1] != 3 or not np.isfinite(pts).all(): raise CadgitError(f"Invalid points: {prim.GetPath()}")
        if counts.ndim != 1 or (counts < 3).any() or counts.sum() != len(indices): raise CadgitError(f"Invalid topology: {prim.GetPath()}")
        if len(indices) and (indices.min() < 0 or indices.max() >= len(pts)): raise CadgitError(f"Out-of-range indices: {prim.GetPath()}")
        transform = cache.GetLocalToWorldTransform(prim) * conversion
        p4 = np.column_stack([pts, np.ones(len(pts))]) @ np.array(transform)
        worldpts = p4[:, :3]
        if not np.isfinite(worldpts).all():raise CadgitError(f"Non-finite world-space geometry: {prim.GetPath()}")
        faces = []; i = 0
        reverse = (np.linalg.det(np.array(transform)[:3,:3]) < 0) != (mesh.GetOrientationAttr().Get() == "leftHanded")
        holes = set(mesh.GetHoleIndicesAttr().Get() or [])
        for face_idx, count in enumerate(counts):
            ids = indices[i:i+count]; i += count
            if face_idx in holes: continue
            if reverse: ids = ids[::-1]
            faces.extend([int(count), *ids.tolist()])
        color = (0.66, 0.72, 0.78)
        display = mesh.GetDisplayColorAttr().Get()
        if display: color = tuple(float(x) for x in display[0])
        material, relation = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()
        matname = None;metallic=0.0;roughness=0.4
        if material:
            matname = material.GetPrim().GetName()
            shader = material.ComputeSurfaceSource()[0]
            if shader:
                value = shader.GetInput("diffuseColor").Get()
                if value is not None: color = tuple(float(x) for x in value)
                for parameter in ['metallic','roughness']:
                    value=shader.GetInput(parameter).Get()
                    if isinstance(value,(float,int)) and math.isfinite(value):
                        if parameter=='metallic':metallic=max(0.,min(1.,float(value)))
                        else:roughness=max(0.,min(1.,float(value)))
        warnings = []
        if mesh.GetSubdivisionSchemeAttr().Get() != "none": warnings.append("Subdivision displayed as authored base mesh")
        if prim.HasAPI(UsdShade.MaterialBindingAPI) or material: warnings.append("Material shown as a basic color; native shaders are not evaluated")
        output.append({"path": str(prim.GetPath()), "name": prim.GetName(), "points": worldpts, "faces": np.array(faces, dtype=np.int64), "color": color, "material_name": matname, "metallic":metallic,"roughness":roughness, "warnings": warnings, "subdivision": mesh.GetSubdivisionSchemeAttr().Get()})
    return output


def stage_info(path):
    stage = open_stage(path); items = []
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdGeom.Mesh) or prim.IsA(UsdGeom.Xform):
            items.append({"path": str(prim.GetPath()), "name": prim.GetName(), "type": prim.GetTypeName()})
    unsupported = sorted({p.GetTypeName() for p in stage.Traverse() if p.GetTypeName() and p.GetTypeName() not in {"Mesh", "Xform", "Scope", "Material", "Shader", "NodeGraph", "GeomSubset"}})
    return {"prims": items, "units": UsdGeom.GetStageMetersPerUnit(stage), "up_axis": str(UsdGeom.GetStageUpAxis(stage)), "unsupported_types": unsupported}


def bind_library_preview(stage,target,material,library,path):
    """Project supported appearance into USD; retain native graphs separately."""
    appearance=material['definition'].get('appearance',{})
    if not appearance:return
    stage.DefinePrim('/World/Looks','Scope')
    usd_material=UsdShade.Material.Define(stage,path)
    if not stage.GetPrimAtPath(path+'/Preview'):
        preview=appearance.get('preview',{})
        shader=UsdShade.Shader.Define(stage,path+'/Preview');shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*preview.get('base_color',[.65,.65,.65])))
        for key,default in [('roughness',.4),('metallic',0.),('opacity',1.)]:shader.CreateInput(key,Sdf.ValueTypeNames.Float).Set(float(preview.get(key,default)))
        usd_material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
        channels={'base_color':('diffuseColor','rgb',Sdf.ValueTypeNames.Float3),'roughness':('roughness','r',Sdf.ValueTypeNames.Float),'metallic':('metallic','r',Sdf.ValueTypeNames.Float),'opacity':('opacity','r',Sdf.ValueTypeNames.Float)}
        from .library import reference
        for role,value in appearance.get('maps',{}).items():
            if role not in channels:continue
            if isinstance(value,dict) and value.get('color_space','raw') not in {'raw','sRGB','auto'}:continue
            image=library.get(reference(value));texture=UsdShade.Shader.Define(stage,path+'/Map_'+role);texture.CreateIdAttr('UsdUVTexture')
            texture.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(str(library.project.stage_path(image))))
            texture.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set(value.get('color_space','sRGB' if role=='base_color' else 'raw') if isinstance(value,dict) else ('sRGB' if role=='base_color' else 'raw'))
            reader=UsdShade.Shader.Define(stage,path+'/ST_'+role);reader.CreateIdAttr('UsdPrimvarReader_float2');reader.CreateInput('varname',Sdf.ValueTypeNames.Token).Set(value.get('uv_set','st') if isinstance(value,dict) else 'st');reader.CreateOutput('result',Sdf.ValueTypeNames.Float2)
            texture.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(),'result')
            input_name,output_name,value_type=channels[role];texture.CreateOutput(output_name,value_type)
            shader.GetInput(input_name).ConnectToSource(texture.ConnectableAPI(),output_name)
    UsdShade.MaterialBindingAPI.Apply(target).Bind(usd_material)


def assemble(project, selections, label="Untitled assembly"):
    try:selections = [Selection.model_validate(s) for s in selections]
    except ValueError as exc:raise CadgitError('Invalid assembly selection: '+str(exc)) from exc
    if not selections: raise CadgitError("Add at least one selection")
    for selection in selections:check_compatibility(selection.model_dump(),"Assembly selection",legacy=True)
    aid = uid("assembly")
    with project.lock():
        staging = project.root / ".cadgit/staging" / aid; staging.mkdir()
        stage = Usd.Stage.CreateNew(str(staging / "scene.usda"))
        root = UsdGeom.Xform.Define(stage, "/World"); stage.SetDefaultPrim(root.GetPrim())
        UsdGeom.SetStageUpAxis(stage, "Z"); UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        warnings = []; bindings = [];library_bindings=[]
        from .library import Library,FEATURE
        library=Library(project)
        for n, sel in enumerate(selections):
            if sel.material_revision and sel.library_material_revision:raise CadgitError('Choose a library material or a captured shader, not both')
            chosen_library=library._require(sel.library_material_revision,{'material'}) if sel.library_material_revision else None
            record = project.resolve(sel.snapshot_id)
            sel.snapshot_id = record["id"]
            if not project.verify(record["id"])["ok"]: raise CadgitError("Source hash verification failed")
            src = open_stage(project.stage_path(record)); source = src.GetPrimAtPath(sel.prim_path)
            if not source or source.IsInstanceProxy(): raise CadgitError("Choose a real prim/subtree (individual instance proxies are not supported yet)")
            if not UsdGeom.Xformable(source): raise CadgitError("Choose a geometric Mesh/Xform prim")
            flat = src.Flatten()
            dest = Sdf.Path(f"/World/Piece_{n+1}_{Sdf.Path.MakeValidIdentifier(sel.label) if hasattr(Sdf.Path, 'MakeValidIdentifier') else 'asset'}")
            # Prefix root names deterministically; leaf mesh names remain known for material mapping.
            if not Sdf.CopySpec(flat, source.GetPath(), stage.GetRootLayer(), dest): raise CadgitError("Cannot copy selected USD subtree")
            copied = stage.GetPrimAtPath(dest)
            xf = UsdGeom.Xformable(copied)
            # Snapshot inspection time is explicit and currently fixed to time zero.
            world = UsdGeom.XformCache(Usd.TimeCode(0)).GetLocalToWorldTransform(source) * basis(src)
            world *= Gf.Matrix4d().SetTranslate(Gf.Vec3d(*sel.translation))
            if not np.isfinite(np.asarray(world)).all():raise CadgitError("Assembly transform contains non-finite values")
            xf.ClearXformOpOrder(); xf.SetResetXformStack(False); xf.AddTransformOp().Set(world)
            copied.SetDisplayName(sel.label)
            copied.CreateAttribute("userProperties:cadgit:selection", Sdf.ValueTypeNames.String).Set(f"{aid}:{n}")
            for child in Usd.PrimRange(source):
                if child != source and UsdGeom.Xformable(child) and UsdGeom.Xformable(child).GetResetXformStack():
                    raise CadgitError("Selected subtree has reset transform stacks; select individual mesh roots instead")
                target_path = child.GetPath().ReplacePrefix(source.GetPath(), dest)
                target = stage.GetPrimAtPath(target_path)
                if not target or not (child.IsA(UsdGeom.Mesh) or child.IsA(UsdGeom.Subset)): continue
                bound = UsdShade.MaterialBindingAPI(child).ComputeBoundMaterial()[0]
                matname = bound.GetPrim().GetName() if bound else None
                if bound:
                    mat_dest = Sdf.Path(f"/World/Looks/S{n}_{bound.GetPrim().GetName()}")
                    stage.DefinePrim("/World/Looks", "Scope")
                    if not stage.GetPrimAtPath(mat_dest): Sdf.CopySpec(flat, bound.GetPath(), stage.GetRootLayer(), mat_dest)
                    UsdShade.MaterialBindingAPI.Apply(target).Bind(UsdShade.Material(stage.GetPrimAtPath(mat_dest)))
                inherited_library=child.GetAttribute('userProperties:cadgit:library_material_revision').Get()
                logical=sel.library_material_revision or (inherited_library if not sel.material_revision else None)
                if logical:
                    material=chosen_library or library._require(logical,{'material'})
                    target.CreateAttribute('userProperties:cadgit:library_material_revision',Sdf.ValueTypeNames.String).Set(logical)
                    if target.IsA(UsdGeom.Mesh):
                        inherited_binding=next((b for b in record.get('library_bindings',[]) if b['prim_path']==str(child.GetPath())),{})
                        policy='library' if chosen_library else inherited_binding.get('appearance_source','library')
                        target.CreateAttribute('userProperties:cadgit:library_appearance_source',Sdf.ValueTypeNames.String).Set(policy)
                        library_bindings.append({'prim_path':str(target_path),'library_material_revision':logical,'appearance_source':policy})
                    if chosen_library:
                        bind_library_preview(stage,target,material,library,f'/World/Looks/Library_{n+1}')
                        if material['definition'].get('appearance',{}).get('maps'):warnings.append('Texture references are pinned; texture rendering requires compatible UVs. Only base_color, roughness, metallic and opacity maps in supported raw/sRGB/auto color spaces are projected to USD.')
                elif sel.material_revision and target.HasAttribute('userProperties:cadgit:library_material_revision'):
                    target.RemoveProperty('userProperties:cadgit:library_material_revision')
                native = sel.material_revision or record.get('metadata',{}).get('native_materials_by_prim',{}).get(str(child.GetPath())) or child.GetAttribute("userProperties:cadgit:material_revision").Get() or record.get("metadata", {}).get("native_materials", {}).get(matname)
                if chosen_library and chosen_library['definition'].get('appearance'):
                    native=None
                    if target.HasAttribute('userProperties:cadgit:material_revision'):target.RemoveProperty('userProperties:cadgit:material_revision')
                if native:
                    material=next((m for m in project.records('materials') if m['id']==native),None)
                    if material is None:raise CadgitError(f'Missing native material: {native}')
                    if not project.verify(material)['ok']:raise CadgitError(f'Material integrity verification failed: {native}')
                    target.CreateAttribute("userProperties:cadgit:material_revision", Sdf.ValueTypeNames.String).Set(native)
                    bindings.append({"prim_path": str(target_path), "material_revision": native})
            # Flatten resolves asset paths into the immutable snapshot package, which remains pinned.
            warnings.append("Animation is sampled at time 0 for placement; nested animated transforms/material subsets require review")
        stage.GetRootLayer().Save()
        # Localize dependencies so this assembly is independently reopenable within the project.
        from pxr import UsdUtils
        if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(staging / "scene.usda")), str(staging / "scene.usdz")):
            raise CadgitError("Assembly dependency packaging failed")
        r = Assembly(id=aid, created_at=now(), label=label, selections=selections).model_dump()
        r.update(entry_layer="scene.usdz", bindings=bindings,library_bindings=library_bindings, warnings=sorted(set(warnings)))
        if library_bindings:r["required_features"]=[FEATURE]
        atomic_json(staging / "recipe.json", {"schema_version": 1, "selections": [s.model_dump() for s in selections], "bindings": bindings,"library_bindings":library_bindings})
        return project.commit(staging, project.root / "assemblies" / aid, r)


def export_stl(project, ref, output=None, select=None, units="mm", allow_issues=False, allow_base_mesh=False):
    import pyvista as pv
    if units not in {"mm", "m", "cm", "in"}: raise CadgitError("Units must be mm, cm, m, or in")
    output=Path(output).expanduser().absolute() if output else None
    if output and output.suffix.lower()!='.stl':raise CadgitError('STL output must end with .stl')
    if output and (output.exists() or output.is_symlink()):raise CadgitError(f'Output already exists: {output}')
    record = project.resolve(ref)
    if not project.verify(record["id"])["ok"]: raise CadgitError("Source integrity verification failed")
    parts = meshes(project.stage_path(record), select)
    if not parts: raise CadgitError("Selection contains no supported visible mesh geometry")
    if any(p["subdivision"] != "none" for p in parts) and not allow_base_mesh:
        raise CadgitError("USD requests subdivision; this exporter supports base polygon meshes. Explicitly enable base-mesh export to proceed.")
    factor = {"m": 1.0, "mm": 1000.0, "cm": 100.0, "in": 1/0.0254}[units]
    geometries = [pv.PolyData(p["points"] * factor, p["faces"]).triangulate() for p in parts]
    combined = geometries[0]
    for mesh in geometries[1:]: combined = combined.merge(mesh, merge_points=False)
    clean = combined.clean(tolerance=1e-9, absolute=True)
    triangles = np.asarray(combined.faces).reshape(-1, 4)[:, 1:]
    points = np.asarray(combined.points)
    cross = np.cross(points[triangles[:,1]]-points[triangles[:,0]], points[triangles[:,2]]-points[triangles[:,0]])
    degenerate = int(np.count_nonzero(np.linalg.norm(cross, axis=1) <= 1e-14))
    edge_count = clean.extract_feature_edges(boundary_edges=True, non_manifold_edges=True, feature_edges=False, manifold_edges=False).n_cells
    report = {"triangles": len(triangles), "mesh_count": len(parts), "degenerate_triangles": degenerate, "boundary_or_nonmanifold_edges": edge_count, "dimensions": list(np.asarray(combined.bounds)[1::2]-np.asarray(combined.bounds)[::2]), "units": units, "self_intersections": "not checked", "wall_thickness": "not checked", "combination": "concatenated shells, not boolean union", "source_mesh": "authored base polygons", "printability_certified": False}
    if degenerate: raise CadgitError(f"Mesh has {degenerate} degenerate triangles")
    if edge_count and not allow_issues: raise CadgitError(f"Mesh has {edge_count} open/nonmanifold edges. Explicitly allow mesh issues to export.")
    with project.lock():
        aid = uid("print"); staging = project.root / ".cadgit/staging" / aid; staging.mkdir()
        target = staging / "part.stl"
        # Binary STL writer; source geometry has already been structurally validated.
        normals = cross / np.linalg.norm(cross, axis=1)[:,None]
        with target.open("wb") as f:
            f.write(b"CAD-GIT; numeric units recorded in manifest".ljust(80,b" "))
            f.write(struct.pack("<I", len(triangles)))
            for normal, ids in zip(normals, triangles):
                f.write(struct.pack("<12fH", *normal.tolist(), *points[ids].ravel().tolist(), 0))
        atomic_json(staging / "validation.json", report)
        r = {"schema_version": 1, "id": aid, "created_at": now(), "label": f"{record['label']} STL", "source_id": record["id"], "selection": select, "format": "stl", "report": report, "entry_layer": "part.stl"}
        result = project.commit(staging, project.root / "artifacts/prints" / aid, r)
        if output:
            try:publish_file(Path(result['_directory'])/'part.stl',output)
            except Exception as exc:raise CadgitError(f'Artifact {result["id"]} is committed; output publication failed: {exc}. Export it to a new destination.') from exc
        return result


def export_usd(project,ref,output):
    """Verified USD export with atomic, race-safe, non-overwriting publication."""
    import tempfile
    from pxr import UsdUtils
    output=Path(output).expanduser().absolute()
    if output.suffix.lower() not in {'.usd','.usda','.usdc','.usdz'}:raise CadgitError('Choose a .usd, .usda, .usdc or .usdz filename')
    if output.exists() or output.is_symlink():raise CadgitError(f'Output already exists: {output}')
    record=project.resolve(ref)
    if not project.verify(record)['ok']:raise CadgitError('Source integrity verification failed')
    with tempfile.TemporaryDirectory(prefix='export-',dir=project.root/'.cadgit/staging') as temporary:
        staged=Path(temporary)/('scene'+output.suffix.lower())
        if output.suffix.lower()=='.usdz':
            if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(project.stage_path(record))),str(staged)):raise CadgitError('USD dependency packaging failed')
        elif not open_stage(project.stage_path(record)).Export(str(staged)):raise CadgitError('USD export failed')
        if not Usd.Stage.Open(str(staged)):raise CadgitError('Exported USD validation failed')
        publish_file(staged,output)
    return {'output':str(output),'source_id':record['id'],'mode':'packaged' if output.suffix.lower()=='.usdz' else 'flattened'}
