"""Rebuild desktop icon assets from the editable SVG (requires PySide6)."""
from pathlib import Path
import subprocess
import sys
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer

resources=Path(__file__).resolve().parents[1]/'src/cadgit/resources'
renderer=QSvgRenderer(str(resources/'cad-git.svg'))
if not renderer.isValid():raise RuntimeError('Invalid icon SVG')

def render(size,path):
    image=QImage(size,size,QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter=QPainter(image);renderer.render(painter);painter.end()
    if not image.save(str(path)):raise RuntimeError('Could not write '+str(path))

render(1024,resources/'cad-git.png')
if sys.platform=='darwin':
    with tempfile.TemporaryDirectory(prefix='cadgit-icon-') as folder:
        iconset=Path(folder)/'cad-git.iconset';iconset.mkdir()
        for size in (16,32,128,256,512):
            render(size,iconset/f'icon_{size}x{size}.png')
            render(size*2,iconset/f'icon_{size}x{size}@2x.png')
        subprocess.run(['iconutil','--convert','icns',str(iconset),'--output',str(resources/'cad-git.icns')],check=True)
print('Rebuilt CAD-GIT desktop icons')
