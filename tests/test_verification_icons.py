"""Exercise the real SVG/raster tool in disposable resource directories."""

from pathlib import Path

import pytest
from PySide6.QtGui import QImage
from PySide6.QtSvg import QSvgRenderer
from test_verification_campaign import script

icons = script("build_icon")
SVG = Path(__file__).resolve().parents[1] / "src/cadgit/resources/cad-git.svg"


def test_icon_builder_renders_real_png_and_macos_iconset(tmp_path):
    source = SVG.read_bytes()
    (tmp_path / "cad-git.svg").write_bytes(source)
    icons.main(tmp_path)
    image = QImage(str(tmp_path / "cad-git.png"))
    assert not image.isNull() and image.width() == image.height() == 1024
    assert (tmp_path / "cad-git.svg").read_bytes() == source
    if icons.sys.platform == "darwin":
        data = (tmp_path / "cad-git.icns").read_bytes()
        assert data[:4] == b"icns" and len(data) > 1000


def test_invalid_svg_and_unwritable_output_fail_actionably(tmp_path):
    (tmp_path / "cad-git.svg").write_text("invalid")
    with pytest.raises(RuntimeError, match="Invalid icon SVG"):
        icons.main(tmp_path)
    assert not (tmp_path / "cad-git.png").exists()
    renderer = QSvgRenderer(str(SVG))
    with pytest.raises(RuntimeError, match="Could not write"):
        icons.render(renderer, 16, tmp_path / "missing" / "icon.png")


def test_icon_cli_can_build_disposable_resources(tmp_path):
    import subprocess
    import sys

    (tmp_path / "cad-git.svg").write_bytes(SVG.read_bytes())
    result = subprocess.run(
        [
            sys.executable,
            str(SVG.parents[3] / "scripts/build_icon.py"),
            "--resources",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Rebuilt Git CAD desktop icons" in result.stdout
    assert not QImage(str(tmp_path / "cad-git.png")).isNull()
