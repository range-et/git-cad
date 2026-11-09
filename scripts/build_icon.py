"""Rebuild desktop icon assets from the editable SVG (requires PySide6)."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer


def render(renderer,size,path):
    image=QImage(size,size,QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter=QPainter(image);renderer.render(painter);painter.end()
    if not image.save(str(path)):raise RuntimeError('Could not write '+str(path))


def main(resources=None):
    resources=Path(resources) if resources is not None else Path(__file__).resolve().parents[1]/'src/cadgit/resources'
    renderer=QSvgRenderer(str(resources/'cad-git.svg'))
    if not renderer.isValid():raise RuntimeError('Invalid icon SVG')
    render(renderer,1024,resources/'cad-git.png')
    if sys.platform=='darwin':
        with tempfile.TemporaryDirectory(prefix='cadgit-icon-') as folder:
            iconset=Path(folder)/'cad-git.iconset';iconset.mkdir()
            for size in (16,32,128,256,512):
                render(renderer,size,iconset/f'icon_{size}x{size}.png')
                render(renderer,size*2,iconset/f'icon_{size}x{size}@2x.png')
            subprocess.run(['iconutil','--convert','icns',str(iconset),'--output',str(resources/'cad-git.icns')],check=True)
    print('Rebuilt Git CAD desktop icons')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources',type=Path,help='Alternate resource directory containing cad-git.svg')
    main(parser.parse_args().resources)
