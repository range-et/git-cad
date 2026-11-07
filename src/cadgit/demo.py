"""Generated example scenes, clearly marked as samples rather than native saves."""
from pathlib import Path
import tempfile
import numpy as np
from pxr import Usd,UsdGeom,Gf,Vt,UsdShade,Sdf
from .store import Project
from .usd import assemble


def create(root):
    import pyvista as pv
    p=Project.init(root,'Engine study')
    if p.records(): return p
    with tempfile.TemporaryDirectory() as tmp:
        for source,index,label in [('rhino',0,'01 • Block roughout'),('rhino',1,'02 • Cooling fins'),('rhino',2,'03 • Mounting feet'),('blender',0,'01 • Rotor study'),('blender',1,'02 • Rounded housing')]:
            path=Path(tmp)/f'{source}_{index}.usda'
            stage=Usd.Stage.CreateNew(str(path));world=UsdGeom.Xform.Define(stage,'/Engine');stage.SetDefaultPrim(world.GetPrim())
            UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1.0)
            if source=='rhino':
                objects=[('Block',pv.Cube(center=(0,0,0.032),x_length=0.10,y_length=0.07,z_length=0.055),(0.40,0.49,0.57))]
                if index>=1:
                    for k in range(5):objects.append((f'Fin_{k+1}',pv.Cube(center=(0,0,0.01+k*0.011),x_length=0.12,y_length=0.085,z_length=0.003),(0.56,0.64,0.69)))
                if index>=2:
                    for x in [-0.04,0.04]:objects.append((f'Foot_{len(objects)}',pv.Cube(center=(x,0,0),x_length=0.025,y_length=0.105,z_length=0.009),(0.31,0.38,0.43)))
            else:
                objects=[('Rotor',pv.Cylinder(center=(0,0.005,0.04),direction=(0,1,0),radius=0.026,height=0.10,resolution=48).triangulate(),(0.85,0.47,0.16))]
                if index>=1:
                    shell=pv.ParametricSuperEllipsoid(n1=0.5,n2=0.8).scale([0.073,0.025,0.047],inplace=False).translate([0,0.065,0.045],inplace=False)
                    objects.append(('Housing',shell.triangulate(),(0.15,0.53,0.65)))
            for name,poly,color in objects:
                poly=poly.extract_surface(algorithm='dataset_surface').triangulate()
                mesh=UsdGeom.Mesh.Define(stage,'/Engine/'+name)
                mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(np.asarray(poly.points,dtype=np.float32)))
                f=np.asarray(poly.faces).reshape(-1,4)
                mesh.GetFaceVertexCountsAttr().Set([3]*len(f));mesh.GetFaceVertexIndicesAttr().Set(f[:,1:].ravel().tolist());mesh.GetSubdivisionSchemeAttr().Set('none')
                mesh.GetDisplayColorAttr().Set([Gf.Vec3f(*color)])
                mat=UsdShade.Material.Define(stage,'/Engine/Looks/'+name)
                shader=UsdShade.Shader.Define(stage,mat.GetPath().AppendChild('Preview'))
                shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));shader.CreateInput('metallic',Sdf.ValueTypeNames.Float).Set(0.5);shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(0.35)
                mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)
            stage.GetRootLayer().Save()
            p.ingest(path,source,label,metadata={'sample_data':True,'note':'Generated sample, not an actual native save'})
    rhino=[r for r in p.records() if r['source']=='rhino'][-1];blender=[r for r in p.records() if r['source']=='blender'][-1]
    result=assemble(p,[{'snapshot_id':rhino['id'],'prim_path':'/Engine','label':'Mechanical block'},{'snapshot_id':blender['id'],'prim_path':'/Engine','label':'Rotor and housing'}],'Engine • combined study')
    p.set_main(result['id'])
    return p
