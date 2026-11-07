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
    p.set_main(result['id']);create_library(p)
    return p


def create_library(project):
    """Explicit, generated library demonstration; never called on arbitrary open."""
    from .library import Library
    from PySide6 import QtGui,QtCore
    library=Library(project)
    existing=[r for r in library.records() if r['kind']=='material' and 'demo_library' in r.get('tags',[])]
    if existing:return existing[-1]
    provenance={'provider':'CAD-GIT generated demo','license':{'name':'Project-generated sample'},'notes':'Not manufacturer material data; all engineering values remain unspecified.'}
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);image=root/'surface-pattern.png'
        def pattern(a,b):
            canvas=QtGui.QImage(160,160,QtGui.QImage.Format_RGB32);painter=QtGui.QPainter(canvas)
            for y in range(8):
                for x in range(8):painter.fillRect(x*20,y*20,20,20,QtGui.QColor(a if (x+y)%2 else b))
            painter.end();canvas.save(str(image))
        pattern('#337F9E','#B9D5DC');first=library.import_asset(image,'Generated surface pattern',provenance=provenance,tags=['demo_library','generated'])
        spec=root/'PLA-notes.txt';spec.write_text('PLA material record demonstration\n\nDensity and elastic properties are UNSPECIFIED.\nEnter grade-specific manufacturer or measured data, units, conditions and source.\nThis file is not an engineering datasheet or a printability certificate.\n')
        document=library.import_asset(spec,'PLA material notes',provenance=provenance,tags=['demo_library'])
        physical={'properties':{'density':{'value':None,'unit':'kg/m3','status':'unspecified','source':'No grade-specific datasheet supplied'},'youngs_modulus':{'value':None,'unit':'Pa','status':'unspecified','source':'No test data supplied','conditions':'Grade, print direction and test temperature unspecified'}}}
        pla=library.create_material('PLA • engineering record',{'physical':physical,'appearance':{},'documents':[]},provenance=provenance,tags=['demo_library','PLA'])
        library.create_material(pla['label'],{**pla['definition'],'documents':[document['id']]},pla['asset_id'],pla['id'],provenance=provenance,note='Attach specification notes; engineering values remain unknown')
        appearance={'preview':{'base_color':[.18,.48,.62],'roughness':.4,'metallic':0.},'maps':{'base_color':{'revision_id':first['id'],'color_space':'sRGB'}}}
        legacy=library.legacy()
        if legacy:appearance['native_graph']=legacy[0]['id']
        finish=library.create_material('Blue surface • appearance',{'physical':{'properties':{}},'appearance':appearance,'documents':[]},provenance=provenance,tags=['demo_library','appearance'])
        material=library.recombine('PLA + blue surface',library.history(pla['asset_id'])[-1]['id'],finish['id'],'Physical properties from PLA record; appearance from blue finish',provenance)
        # Change the image's head after creating the material. The material keeps v1.
        pattern('#B86F36','#E2C89B');library.import_asset(image,first['label'],asset_id=first['asset_id'],expected_revision=first['id'],provenance=provenance,tags=['demo_library','generated'],note='New warm variant; earlier materials retain the blue revision')
    return material
