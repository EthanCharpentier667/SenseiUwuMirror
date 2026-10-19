"""Regression tests for sandbox container cleanup."""

from pathlib import Path
from unittest.mock import Mock

import docker
import pytest
from requests.exceptions import ReadTimeout

from sensai.features.tools.sandbox.sandboxed_docker import (
    DOCKERFILE_BASH,
    DOCKERFILE_PYTHON,
    MAX_OUTPUT_BYTES,
    SandboxedDocker,
)

APIError = docker.errors.APIError


@pytest.fixture
def container(monkeypatch: pytest.MonkeyPatch) -> Mock:
    mock_container = Mock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = (chunk for chunk in [b"hello\n"])
    client = Mock()
    client.containers.run.return_value = mock_container
    client.images.build.return_value = (Mock(id="sandbox-image"), [])
    monkeypatch.setattr(docker, "from_env", Mock(return_value=client))
    return mock_container


def test_success_returns_output_and_removes_container(container: Mock) -> None:
    assert SandboxedDocker("python").run_code("print('hello')") == "hello\n"

    container.wait.assert_called_once_with(timeout=20)
    container.remove.assert_called_once_with(force=True)


@pytest.mark.parametrize(
    ("language", "dockerfile"),
    [("python", DOCKERFILE_PYTHON), ("bash", DOCKERFILE_BASH)],
)
def test_build_selects_requested_dockerfile(
    container: Mock, language: str, dockerfile: str
) -> None:
    sandbox = SandboxedDocker(language)

    build = docker.from_env().images.build
    build.assert_called_once()
    assert build.call_args.kwargs["dockerfile"] == dockerfile
    assert (Path(build.call_args.kwargs["path"]) / dockerfile).is_file()
    assert sandbox.image == "sandbox-image"


def test_unsupported_language_does_not_build_an_image(container: Mock) -> None:
    with pytest.raises(ValueError, match="Unsupported type"):
        SandboxedDocker("javascript")

    docker.from_env().images.build.assert_not_called()


def test_bash_forwards_command_and_reads_container_output(container: Mock) -> None:
    code = 'printf "%s\\n" "Bash works"'

    assert SandboxedDocker("bash").run_code(code) == "hello\n"

    config = docker.from_env().containers.run.call_args.kwargs
    assert config["command"] == ["-c", code]
    assert config["image"] == "sandbox-image"
    assert config["stdin_open"] is True
    container.attach_socket.assert_not_called()
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
        "/workspace": "rw,nosuid,nodev,size=512m,uid=10001,gid=10001,mode=0700",
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
