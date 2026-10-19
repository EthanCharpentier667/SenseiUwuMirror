"""Verify that sandbox construction and execution stay off the asyncio thread."""

import threading
from typing import Any
from unittest.mock import Mock

import docker
import pytest

from sensai.features.tools.sandbox.sandboxed_code import SandboxedCode


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["python", "bash"])
async def test_build_and_execution_share_a_worker_thread(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    loop_thread = threading.get_ident()
    threads: list[int] = []
    container = Mock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = (chunk for chunk in [b"hello\n"])

    def build(**kwargs: Any) -> tuple[Mock, list[Any]]:
        thread = threading.get_ident()
        assert thread != loop_thread
        threads.append(thread)
        assert kwargs["dockerfile"] == f"Dockerfile.{language}"
        return Mock(id="sandbox-image"), []

    def run(**kwargs: Any) -> Mock:
        thread = threading.get_ident()
        assert thread != loop_thread
        threads.append(thread)
        assert kwargs["command"] == ["-c", "print('hello')"]
        return container

    client = Mock()
    client.images.build.side_effect = build
    client.containers.run.side_effect = run
    monkeypatch.setattr(docker, "from_env", Mock(return_value=client))

    result = await SandboxedCode().execute(language=language, code="print('hello')")

    assert len(threads) == 2
    assert threads[0] == threads[1]
    assert result == {"result": "Executed code: print('hello')", "output": "hello\n"}
    container.remove.assert_called_once_with(force=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["build", "run"])
async def test_worker_errors_propagate(monkeypatch: pytest.MonkeyPatch, failure_stage: str) -> None:
    error = RuntimeError("Docker unavailable")
    client = Mock()
    client.images.build.return_value = (Mock(id="sandbox-image"), [])
    if failure_stage == "build":
        client.images.build.side_effect = error
    else:
        client.containers.run.side_effect = error
    monkeypatch.setattr(docker, "from_env", Mock(return_value=client))

    with pytest.raises(RuntimeError, match="Docker unavailable") as caught:
        await SandboxedCode().execute(language="python", code="print('hello')")

    assert caught.value is error
