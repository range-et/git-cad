"""Desktop branding degrades predictably when optional Cocoa bindings are absent."""

import sys
from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtGui

import cadgit.app_identity as identity


@pytest.mark.parametrize("name", [None, "Test CAD"])
@pytest.mark.parametrize("available", [False, True])
@pytest.mark.parametrize("bundle_info", [None, {}])
def test_cocoa_identity_is_optional_and_qt_names_remain_consistent(
    monkeypatch, available, bundle_info, name
):
    seen = []
    monkeypatch.setattr(identity.sys, "platform", "darwin")
    cocoa = SimpleNamespace(
        NSBundle=SimpleNamespace(
            mainBundle=lambda: SimpleNamespace(infoDictionary=lambda: bundle_info)
        ),
        NSProcessInfo=SimpleNamespace(
            processInfo=lambda: SimpleNamespace(
                setProcessName_=lambda name: seen.append(("process", name))
            )
        ),
    )
    monkeypatch.setitem(sys.modules, "Foundation", cocoa if available else None)
    monkeypatch.setattr(
        QtCore.QCoreApplication,
        "setApplicationName",
        lambda name: seen.append(("application", name)),
    )
    monkeypatch.setattr(
        QtGui.QGuiApplication,
        "setApplicationDisplayName",
        lambda name: seen.append(("display", name)),
    )
    monkeypatch.setattr(
        QtGui.QGuiApplication,
        "setDesktopFileName",
        lambda name: seen.append(("desktop", name)),
    )
    if name is None:
        identity.configure_application_identity()
    else:
        identity.configure_application_identity(name)
    slug = name or "git-cad"
    display = name or "Git CAD"
    assert seen[-3:] == [
        ("application", slug),
        ("display", display),
        ("desktop", "git-cad"),
    ]
    assert (("process", slug) in seen) is available
    if available and bundle_info is not None:
        assert bundle_info == {
            "CFBundleName": display,
            "CFBundleDisplayName": display,
        }


@pytest.mark.parametrize(
    "available,has_image", [(False, False), (True, False), (True, True)]
)
def test_optional_dock_image_keeps_qt_vector_fallback(
    monkeypatch, available, has_image
):
    seen = []
    image = object() if has_image else None
    monkeypatch.setattr(identity.sys, "platform", "darwin")

    def load(path):
        assert path == str(identity.RESOURCES / "cad-git.png")
        return image

    cocoa = SimpleNamespace(
        NSImage=SimpleNamespace(
            alloc=lambda: SimpleNamespace(initWithContentsOfFile_=load)
        ),
        NSApplication=SimpleNamespace(
            sharedApplication=lambda: SimpleNamespace(
                setApplicationIconImage_=lambda value: seen.append(value)
            )
        ),
    )
    monkeypatch.setitem(sys.modules, "AppKit", cocoa if available else None)
    monkeypatch.setattr(QtGui, "QIcon", lambda path: ("vector", path))
    app = SimpleNamespace(setWindowIcon=lambda value: seen.append(value))
    identity.configure_application_icon(app)
    assert seen[0] == ("vector", str(identity.RESOURCES / "cad-git.svg"))
    assert seen[1:] == ([image] if available and has_image else [])
