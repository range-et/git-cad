"""Local protocol boundaries without launching or configuring native applications."""

import io
import json
from unittest.mock import MagicMock

import pytest

from cadgit import connectors
from cadgit.store import CadgitError, Project, atomic_json, read_json


@pytest.mark.parametrize(
    "chunks,expected",
    [
        (
            [b'{"status":', b'"success","result":42}'],
            {"status": "success", "result": 42},
        ),
        ([b'{"status":"error","message":"native rejected"}'], "native rejected"),
        ([b""], "disconnected"),
        ([b"x" * (16 * 1024 * 1024)], "exceeds size limit"),
    ],
)
def test_blender_rpc_framing_and_failure_boundaries(monkeypatch, chunks, expected):
    socket = MagicMock()
    socket.__enter__.return_value = socket
    socket.recv.side_effect = chunks
    connect = MagicMock(return_value=socket)
    monkeypatch.setattr(connectors.socket, "create_connection", connect)
    if isinstance(expected, str):
        with pytest.raises(CadgitError, match=expected):
            connectors.blender_rpc("print(42)", "localhost", 1234)
    else:
        assert connectors.blender_rpc("print(42)", "localhost", 1234) == expected
    connect.assert_called_once_with(("localhost", 1234), timeout=120)
    assert json.loads(socket.sendall.call_args.args[0]) == {
        "type": "execute_code",
        "params": {"code": "print(42)"},
    }
    socket.__exit__.assert_called_once()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_rhino_discovery_rejects_ambiguous_documents(tmp_path, monkeypatch, count):
    monkeypatch.setattr(connectors.Path, "home", lambda: tmp_path)
    listeners = tmp_path / "Library/Application Support/McNeel/Rhinoceros/ai/listeners"
    listeners.mkdir(parents=True)
    (listeners / "broken.json").write_text("bad json")
    (listeners / "stopped-999.json").write_text("{}")
    for i in range(count):
        (listeners / f"doc-{1230 + i}.json").write_text(
            json.dumps({"port": 1230 + i} if i else {})
        )

    def respond(request, timeout):
        assert timeout == 2
        payload = json.loads(request.data)
        assert payload["params"]["name"] == "get_context"
        if ":999/" in request.full_url:
            raise OSError("stopped")
        return io.BytesIO(b'{"result": {}}')

    monkeypatch.setattr(connectors.urllib.request, "urlopen", respond)
    if count == 1:
        assert connectors.rhino_endpoint() == "http://127.0.0.1:1230/"
    else:
        with pytest.raises(CadgitError, match=f"Found {count} Rhino documents"):
            connectors.rhino_endpoint()


@pytest.mark.parametrize(
    "response",
    [{"result": {"value": 42}}, {"error": "bad"}, {"result": {"isError": True}}],
)
def test_rhino_rpc_envelope_and_error_response(monkeypatch, response):
    monkeypatch.setattr(connectors, "rhino_endpoint", lambda: "http://127.0.0.1:1234/")

    def respond(request, timeout):
        assert timeout == 120
        assert request.full_url == "http://127.0.0.1:1234/"
        assert json.loads(request.data) == {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "run_python", "arguments": {"script": "print(42)"}},
        }
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(connectors.urllib.request, "urlopen", respond)
    if "error" in response or response.get("result", {}).get("isError"):
        with pytest.raises(CadgitError):
            connectors.rhino_rpc("print(42)")
    else:
        assert connectors.rhino_rpc("print(42)") == response


def test_attach_persists_endpoint_only_after_native_acceptance(tmp_path, monkeypatch):
    project = Project.init(tmp_path / "project")
    path = project.root / ".cadgit/connections.local.json"
    atomic_json(
        path, {"future": {"preserved": True}, "rhino_endpoint": "http://prior/"}
    )
    before = path.read_bytes()
    rpc = MagicMock(side_effect=OSError("denied"))
    monkeypatch.setattr(connectors, "rhino_rpc", rpc)
    with pytest.raises(OSError, match="denied"):
        connectors.attach(project, "rhino", "http://new/")
    assert path.read_bytes() == before
    rpc.side_effect = None
    rpc.return_value = {"ok": True}
    assert connectors.attach(project, "rhino", "http://new/") == {"ok": True}
    assert read_json(path) == {
        "future": {"preserved": True},
        "rhino_endpoint": "http://new/",
    }
    code, endpoint = rpc.call_args.args
    assert endpoint == "http://new/" and code.startswith(
        "PROJECT = " + repr(str(project.root))
    )
    assert "def cadgit_capture(" in code
    path.unlink()
    monkeypatch.setattr(connectors, "rhino_endpoint", lambda: "http://discovered/")
    connectors.attach(project, "rhino")
    assert read_json(path)["rhino_endpoint"] == "http://discovered/"
    connectors.attach(project, "rhino")
    assert rpc.call_args.args[1] == "http://discovered/"
    blender = MagicMock(return_value={"ok": "blender"})
    monkeypatch.setattr(connectors, "blender_rpc", blender)
    assert connectors.attach(project, "blender") == {"ok": "blender"}
    assert "cadgit_capture" in blender.call_args.args[0]
