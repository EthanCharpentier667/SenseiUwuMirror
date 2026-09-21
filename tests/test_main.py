"""Tests for the ``sensai`` package entry point."""

import pytest

from sensai import main


def test_main_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    captured = capsys.readouterr()
    assert "Hello from sensei-uwu-mirror!" in captured.out
