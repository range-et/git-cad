"""Actual Qt/VTK pixels: packaged textures, mode toggles and draft overrides."""
import sys,tempfile,time
from pathlib import Path
import numpy as np
from PySide6 import QtWidgets as W
from PySide6.QtTest import QTest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_texture_preview import textured_plane
from cadgit.store import Project
from cadgit.library import Library
from cadgit.ui_v2 import Window
from cadgit.models import Selection

app=W.QApplication([]);app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory(prefix='cadgit-texture-ui-') as temporary:
    root=Path(temporary);path,image,_=textured_plane(root);project=Project.init(root/'project');snapshot=project.ingest(path)
    library=Library(project);asset=library.import_asset(image);material=library.create_material('Checker',{'appearance':{'maps':{'base_color':{'revision_id':asset['id']}}}})
    # The original external file is gone: the viewport must read the archived image.
    image.unlink();path.unlink();errors=[]
    window=Window(project);window.fail=lambda value:errors.append(str(value));window.show()
    def settle():
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
            if not window.jobs:return
        raise AssertionError('Texture GUI job timed out')
    def pixels(tab):
        tab.plotter.view_xy();tab.plotter.enable_parallel_projection();tab.plotter.reset_camera();tab.plotter.render();QTest.qWait(100)
        screenshot=tab.plotter.screenshot(return_img=True)
        colors=[]
        for x,y in [(-.5,.5),(.5,.5),(-.5,-.5),(.5,-.5)]:
            renderer=tab.plotter.renderer;renderer.SetWorldPoint(x,y,0,1);renderer.WorldToDisplay();sx,sy,_=renderer.GetDisplayPoint();sx=int(sx);sy=screenshot.shape[0]-1-int(sy)
            colors.append(screenshot[sy-3:sy+4,sx-3:sx+4,:3].mean(axis=(0,1)))
        return np.array(colors),screenshot
    try:
        QTest.qWait(140);settle();tab=window.current();window.mode_changed('Rendered preview')
        rendered,screenshot=pixels(tab)
        assert 'base_color' in tab.material_textures[0]
        assert tab.plotter.actors['mesh_0'].mapper.dataset.active_texture_coordinates.shape==(6,2)
        # All four quadrants must actually appear, not merely exist on the actor.
        assert rendered[0,0]>rendered[0,1]+50 and rendered[0,0]>rendered[0,2]+50,rendered
        assert rendered[1,1]>rendered[1,0]+50 and rendered[1,1]>rendered[1,2]+50,rendered
        assert rendered[2,2]>rendered[2,0]+50 and rendered[2,2]>rendered[2,1]+50,rendered
        assert rendered[3,0]>rendered[3,2]+50 and rendered[3,1]>rendered[3,2]+50,rendered
        from PIL import Image
        Image.fromarray(screenshot).save('/tmp/cadgit-texture-rendered.png')
        window.mode_changed('Shaded');shaded,_=pixels(tab)
        assert np.max(np.ptp(shaded,axis=0))<30,shaded
        window.mode_changed('Rendered preview');again,_=pixels(tab);assert np.allclose(again,rendered,atol=2)
        window.draft=[Selection(snapshot_id=snapshot['id'],prim_path='/World/Plane',library_material_revision=material['id']).model_dump()]
        window.update_tray();window.preview_draft();settle();preview=window.current();window.mode_changed('Rendered preview');draft,_=pixels(preview)
        assert np.allclose(draft,rendered,atol=3),(draft,rendered)
        masked=library.create_material('Masked checker',{'appearance':{'maps':{'base_color':asset['id'],'opacity':asset['id'],'roughness':asset['id'],'metallic':asset['id']}}})
        window.draft=[Selection(snapshot_id=snapshot['id'],prim_path='/World/Plane',library_material_revision=masked['id']).model_dump()]
        window.update_tray();window.preview_draft();settle();preview=window.current();window.mode_changed('Rendered preview');mask,_=pixels(preview)
        assert 'orm' in preview.material_textures[0]
        # The green/blue quadrants have red-channel opacity zero and must show
        # background, rather than opaque green/blue surfaces.
        assert mask[1,1]<rendered[1,1]-50 and mask[2,2]<rendered[2,2]-50,(mask,rendered)
        assert not errors,errors
        print('TEXTURE_PREVIEW_VERIFIED: archived image pixels, indexed UV seams, four rendered quadrants, mode toggles, textured library draft, opacity and ORM maps')
    finally:window.close();app.processEvents()
