"""Set the desktop identity before Qt/Cocoa constructs the application menu."""
import sys
from pathlib import Path

RESOURCES=Path(__file__).parent/'resources'


def configure_application_identity(name='git-cad'):
    display='Git CAD' if name=='git-cad' else name
    if sys.platform=='darwin':
        try:
            from Foundation import NSBundle,NSProcessInfo
            info=NSBundle.mainBundle().infoDictionary()
            if info is not None:
                info['CFBundleName']=display;info['CFBundleDisplayName']=display
            NSProcessInfo.processInfo().setProcessName_(name)
        except ImportError:
            # Other Python distributions may not include PyObjC. Qt's own name
            # still applies; a packaged app's Info.plist supplies Cocoa identity.
            pass
    from PySide6 import QtCore,QtGui
    QtCore.QCoreApplication.setApplicationName(name)
    QtGui.QGuiApplication.setApplicationDisplayName(display)
    QtGui.QGuiApplication.setDesktopFileName('git-cad')


def configure_application_icon(app):
    """Apply the bundled vector icon and Cocoa Dock image after app creation."""
    from PySide6 import QtGui
    app.setWindowIcon(QtGui.QIcon(str(RESOURCES/'cad-git.svg')))
    if sys.platform=='darwin':
        try:
            from AppKit import NSApplication,NSImage
            icon=NSImage.alloc().initWithContentsOfFile_(str(RESOURCES/'cad-git.png'))
            if icon is not None:NSApplication.sharedApplication().setApplicationIconImage_(icon)
        except ImportError:
            pass  # Qt supplies the icon on Python distributions without PyObjC.
