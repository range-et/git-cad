"""CPU-only viewport preparation. No renderer, widget or OpenGL objects here.

Each worker owns its datasets until it returns them to the GUI; they are never
modified concurrently. Source arrays remain available for picking/export.
"""
import numpy as np
import pyvista as pv
from .texture_preview import render_maps


def prepare_parts(parts, cancelled=None):
    prepared=[]
    for part in parts:
        if cancelled is not None and cancelled.is_set():return []
        points=part['points']
        part['_preview_bounds']=(points.min(0),points.max(0)) if len(points) else None
        poly=pv.PolyData(part['points'],part['faces'])
        maps=render_maps(part)
        if maps and len(maps['uv']):
            poly.compute_normals(cell_normals=False,consistent_normals=False,inplace=True)
            # Preserve the smooth source normals across USD's face-corner seams.
            faces=part['faces'];offset=0;starts=[]
            while offset<len(faces):
                starts.append(offset);offset+=int(faces[offset])+1
            mask=np.ones(len(faces),dtype=bool);mask[starts]=False
            ids=faces[mask];render_faces=faces.copy();render_faces[mask]=np.arange(len(ids))
            normals=poly.point_data['Normals'][ids].copy()
            poly=pv.PolyData(part['points'][ids],render_faces)
            poly.point_data['Normals']=normals;poly.point_data.active_normals_name='Normals'
            poly.active_texture_coordinates=maps['uv']
        # Do the expensive normal generation / sharp-edge splitting in the
        # worker, so add_mesh only installs an already evaluated dataset.
        if poly.n_cells>poly.n_verts+poly.n_lines:
            poly=poly.compute_normals(cell_normals=False,split_vertices=True,
                                      feature_angle=30)
        prepared.append((poly,maps))
    return prepared
