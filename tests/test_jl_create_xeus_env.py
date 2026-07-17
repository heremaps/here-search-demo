###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import sys
import types

import pytest


_fake_xeus_pkg = types.ModuleType("jupyterlite_xeus")
_fake_xeus_create_env_mod = types.ModuleType("jupyterlite_xeus.create_conda_env")
_fake_xeus_create_env_mod.create_conda_env_from_specs = lambda **_kwargs: None
sys.modules.setdefault("jupyterlite_xeus", _fake_xeus_pkg)
sys.modules.setdefault("jupyterlite_xeus.create_conda_env", _fake_xeus_create_env_mod)

from jupyterlite_build.xeus import create_env as create_xeus_env  # noqa: E402


def test_create_conda_env_from_specs_micromamba_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(create_xeus_env.shutil, "which", lambda _name: None)

    with pytest.raises(RuntimeError, match="micromamba is needed"):
        create_xeus_env.create_conda_env_from_specs_micromamba(
            env_name=create_xeus_env.ENV_NAME,
            root_prefix=tmp_path / "root",
            specs=["python"],
            channels=["https://conda.anaconda.org/conda-forge"],
        )


def test_create_conda_env_from_specs_micromamba_builds_expected_command(monkeypatch, tmp_path):
    monkeypatch.setattr(create_xeus_env.shutil, "which", lambda _name: "/usr/bin/micromamba")
    calls: list[tuple[list[str], bool]] = []

    def _fake_run(cmd, check):
        calls.append((cmd, check))

    monkeypatch.setattr(create_xeus_env.subprocess, "run", _fake_run)

    root_prefix = tmp_path / "prefix-root"
    create_xeus_env.create_conda_env_from_specs_micromamba(
        env_name="xeus-kernels",
        root_prefix=root_prefix,
        specs=["xeus-python", "numpy"],
        channels=["https://conda.anaconda.org/conda-forge", "https://repo.prefix.dev/emscripten-forge-dev"],
        verbose=True,
    )

    assert calls
    cmd, check = calls[0]
    assert check is True
    assert cmd[0] == "/usr/bin/micromamba"
    assert "--prefix" in cmd
    assert str(root_prefix / "envs" / "xeus-kernels") in cmd
    assert f"--platform={create_xeus_env.PLATFORM}" in cmd
    assert "-vvv" in cmd
    assert cmd[-3:] == ["xeus-python", "numpy", "-vvv"]


def test_main_dispatches_to_create_conda_env(monkeypatch, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\ndependencies = []\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_env.py",
            "--root-prefix",
            str(tmp_path / "root"),
            "--pyproject",
            str(pyproject),
            "--extras",
            "dev",
            "lab",
        ],
    )

    collect_calls = []
    create_calls = []

    def _fake_collect_specs(project, extras, base_line_spec):
        collect_calls.append((project, extras, base_line_spec))
        return {"a": "xeus-python", "b": "numpy"}

    def _fake_create_conda_env_from_specs(*, env_name, root_prefix, specs, channels):
        create_calls.append((env_name, root_prefix, specs, channels))

    monkeypatch.setattr(create_xeus_env, "collect_specs", _fake_collect_specs)
    monkeypatch.setattr(create_xeus_env, "create_conda_env_from_specs", _fake_create_conda_env_from_specs)

    create_xeus_env.main()

    assert len(collect_calls) == 1
    _, extras, baseline = collect_calls[0]
    assert extras == ["dev", "lab"]
    assert baseline == create_xeus_env.XEUS_RUNTIME

    assert len(create_calls) == 1
    env_name, root_prefix, specs, channels = create_calls[0]
    assert env_name == create_xeus_env.ENV_NAME
    assert specs == ["xeus-python", "numpy"]
    assert channels == create_xeus_env.XEUS_CHANNELS
    assert str(root_prefix).endswith("/root")


def test_main_dispatches_to_micromamba_when_flag_enabled(monkeypatch, tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\ndependencies = []\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "create_env.py",
            "--root-prefix",
            str(tmp_path / "root"),
            "--pyproject",
            str(pyproject),
            "--extras",
            "xeus_build",
            "--micromamba",
        ],
    )

    monkeypatch.setattr(create_xeus_env, "collect_specs", lambda *_args, **_kwargs: {"k": "xeus-python"})
    micromamba_calls = []

    def _fake_micromamba(*, env_name, root_prefix, specs, channels, verbose):
        micromamba_calls.append((env_name, root_prefix, specs, channels, verbose))

    monkeypatch.setattr(create_xeus_env, "create_conda_env_from_specs_micromamba", _fake_micromamba)

    create_xeus_env.main()

    assert len(micromamba_calls) == 1
    env_name, _root_prefix, specs, channels, verbose = micromamba_calls[0]
    assert env_name == create_xeus_env.ENV_NAME
    assert specs == ["xeus-python"]
    assert channels == create_xeus_env.XEUS_CHANNELS
    assert verbose is True
