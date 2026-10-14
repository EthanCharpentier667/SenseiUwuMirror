"""Regression tests for sandbox container cleanup."""

import io
import socket
import tarfile
from pathlib import Path
from unittest.mock import Mock

import docker
import pytest
from requests.exceptions import ReadTimeout

import sensai.features.tools.sandbox.sandboxed_docker as sandbox_module
from sensai.features.tools.sandbox.sandboxed_docker import MAX_OUTPUT_BYTES, SandboxedDocker
from sensai.features.tools.sandbox.sandboxed_docker import copy_project as send_project

APIError = docker.errors.APIError


@pytest.fixture
def container(monkeypatch: pytest.MonkeyPatch) -> Mock:
    mock_container = Mock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = (chunk for chunk in [b"hello\n"])
    client = Mock()
    client.containers.run.return_value = mock_container
    monkeypatch.setattr(docker, "from_env", Mock(return_value=client))
    monkeypatch.setattr(SandboxedDocker, "_build_image_python", Mock(return_value="sandbox-image"))
    monkeypatch.setattr(SandboxedDocker, "_build_image_bash", Mock(return_value="bash-image"))
    return mock_container


def test_success_returns_output_and_removes_container(container: Mock) -> None:
    assert SandboxedDocker("python").run_code("print('hello')") == "hello\n"

    container.wait.assert_called_once_with(timeout=20)
    container.remove.assert_called_once_with(force=True)


@pytest.mark.parametrize("error_type", [ReadTimeout, APIError])
def test_wait_failure_forces_cleanup_and_propagates_error(
    container: Mock, error_type: type[Exception]
) -> None:
    error = error_type("Wait failed")
    container.wait.side_effect = error

    with pytest.raises(error_type) as caught:
        SandboxedDocker("python").run_code("while True: pass")

    assert caught.value is error
    container.logs.assert_not_called()
    container.remove.assert_called_once_with(force=True)


def test_nonzero_exit_reports_error_and_removes_container(container: Mock) -> None:
    container.wait.return_value = {"StatusCode": 1}
    container.logs.return_value = (chunk for chunk in [b"Execution failed"])

    with pytest.raises(RuntimeError, match=r"Error executing code.*Execution failed"):
        SandboxedDocker("python").run_code("raise ValueError()")

    container.remove.assert_called_once_with(force=True)


@pytest.mark.parametrize("exit_code", [0, 1])
def test_log_failure_still_removes_container(container: Mock, exit_code: int) -> None:
    container.wait.return_value = {"StatusCode": exit_code}
    error = APIError("Logs unavailable")
    container.logs.side_effect = error

    with pytest.raises(APIError) as caught:
        SandboxedDocker("python").run_code("print('hello')")

    assert caught.value is error
    container.remove.assert_called_once_with(force=True)


def test_decode_failure_still_removes_container(container: Mock) -> None:
    container.logs.return_value = (chunk for chunk in [b"\xff"])

    with pytest.raises(UnicodeDecodeError):
        SandboxedDocker("python").run_code("print('hello')")

    container.remove.assert_called_once_with(force=True)


def test_log_retention_is_finite(container: Mock) -> None:
    SandboxedDocker("python").run_code("print('hello')")

    config = docker.from_env().containers.run.call_args.kwargs["log_config"]
    assert config.type == "local"
    assert config.config == {"max-size": "1m", "max-file": "1", "compress": "false"}


def test_cpu_has_a_hard_quota(container: Mock) -> None:
    SandboxedDocker("python").run_code("print('hello')")

    config = docker.from_env().containers.run.call_args.kwargs
    assert config["nano_cpus"] == 500_000_000
    assert "cpu_shares" not in config


def test_writes_are_restricted_to_size_limited_tmpfs(container: Mock) -> None:
    SandboxedDocker("python").run_code("print('hello')")

    config = docker.from_env().containers.run.call_args.kwargs
    assert config["read_only"] is True
    assert config["tmpfs"] == {
        "/workspace": "rw,noexec,nosuid,nodev,size=512m,uid=10001,gid=10001,mode=0700",
        "/tmp": (  # noqa: S108 - Private container mount, not a host temporary file.
            "rw,noexec,nosuid,nodev,size=16m,uid=10001,gid=10001,mode=0700"
        ),
    }


@pytest.mark.parametrize("exit_code", [0, 1])
def test_output_is_bounded_before_decoding(container: Mock, exit_code: int) -> None:
    container.wait.return_value = {"StatusCode": exit_code}
    logs = Mock()
    logs.__iter__ = Mock(return_value=iter([b"a" * (MAX_OUTPUT_BYTES - 1), b"b\xff", b"unused"]))
    container.logs.return_value = logs
    expected = "a" * (MAX_OUTPUT_BYTES - 1) + "b"

    if exit_code == 0:
        assert SandboxedDocker("python").run_code("print('hello')") == expected
    else:
        with pytest.raises(RuntimeError) as caught:
            SandboxedDocker("python").run_code("raise ValueError()")
        assert str(caught.value) == f"Error executing code in sandboxed environment: {expected}"

    container.logs.assert_called_once_with(stream=True, follow=False)
    assert next(logs.__iter__.return_value) == b"unused"
    logs.close.assert_called_once_with()
    container.remove.assert_called_once_with(force=True)


def test_utf8_survives_chunk_boundaries(container: Mock) -> None:
    container.logs.return_value = (chunk for chunk in [b"caf\xc3", b"\xa9\n"])

    assert SandboxedDocker("python").run_code("print('café')") == "café\n"


def test_truncation_omits_incomplete_utf8_character(container: Mock) -> None:
    prefix = b"a" * (MAX_OUTPUT_BYTES - 1)
    container.logs.return_value = (chunk for chunk in [prefix, "é".encode()])

    assert SandboxedDocker("python").run_code("print('hello')") == prefix.decode()


def test_project_archive_is_sent_to_stdin_without_hidden_files(
    container: Mock, tmp_path: Path
) -> None:
    (tmp_path / "main.c").write_text("int main(void) { return 0; }", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=example", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("private", encoding="utf-8")
    transport = Mock()
    connection = Mock(_sock=transport)
    container.attach_socket.return_value = connection

    send_project(container, tmp_path)

    data = b"".join(call.args[0] for call in transport.sendall.call_args_list)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        assert archive.getnames() == [".", "./main.c"]
        content = archive.extractfile("./main.c")
        assert content is not None
        assert content.read() == b"int main(void) { return 0; }"
        assert archive.getmember("./main.c").uid == 10001

    container.put_archive.assert_not_called()
    container.attach_socket.assert_called_once_with(params={"stdin": True, "stream": True})
    transport.shutdown.assert_called_once_with(socket.SHUT_WR)
    connection.close.assert_called_once_with()


def test_bash_extracts_project_before_running_code(
    container: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy = Mock()
    monkeypatch.setattr(sandbox_module, "copy_project", copy)
    code = 'printf "%s" "quoted command"'

    assert SandboxedDocker("bash").run_code(code) == "hello\n"

    config = docker.from_env().containers.run.call_args.kwargs
    assert config["read_only"] is True
    assert config["stdin_open"] is True
    command = config["command"]
    assert "tar --extract" in command[1]
    assert '&& exec /bin/bash -c "$1"' in command[1]
    assert command[-1] == code
    copy.assert_called_once_with(container, Path.cwd())
    container.remove.assert_called_once_with(force=True)


def test_project_transfer_failure_still_removes_container(
    container: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sandbox_module, "copy_project", Mock(side_effect=OSError("Transfer failed"))
    )

    with pytest.raises(OSError, match="Transfer failed"):
        SandboxedDocker("bash").run_code("ls")

    container.wait.assert_not_called()
    container.remove.assert_called_once_with(force=True)
