###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""Create a xeus-python conda prefix from pyproject.toml dependencies.

The resulting prefix can be passed to jupyter lite build via
--XeusAddon.prefix=<root_prefix>/envs/xeus-kernels

Usage::

    python jupyterlite_build/create_env.py \\
        --root-prefix /path/to/workspace/_xeus-prefix-root \\
        --pyproject /path/to/pyproject.toml \\
        [--extras route]
"""

import argparse
import shutil
import subprocess
import tomllib
from pathlib import Path

from jupyterlite_xeus.create_conda_env import create_conda_env_from_specs

from jupyterlite_build.pyproject_toml import collect_specs

XEUS_RUNTIME = ["xeus-python", "xeus-python-shell", "xeus-python-shell-lite"]
XEUS_CHANNELS = [
    "https://conda.anaconda.org/conda-forge",
    # "https://repo.prefix.dev/emscripten-forge-4x",  # Broken pyproj
    "https://repo.prefix.dev/emscripten-forge-dev",
]
ENV_NAME = "xeus-kernels"
PLATFORM = "emscripten-wasm32"


def create_conda_env_from_specs_micromamba(
    env_name: str,
    root_prefix: Path,
    specs: list[str],
    channels: list[str],
    verbose: bool = False,
) -> None:
    micromamba = shutil.which("micromamba")
    if not micromamba:
        raise RuntimeError(
            "micromamba is needed for creating the emscripten environment. "
            "Please install it using conda `conda install micromamba -c conda-forge` "
            "or from https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html"
        )

    root_prefix = Path(root_prefix)
    prefix = root_prefix / "envs" / env_name
    root_prefix.mkdir(parents=True, exist_ok=True)

    channels_args: list[str] = []
    for channel in channels:
        channels_args.extend(["-c", channel])

    cmd = [
        micromamba,
        "create",
        "--yes",
        "--no-pyc",
        "--prefix",
        str(prefix),
        "--relocate-prefix",
        "",
        "--root-prefix",
        str(root_prefix),
        f"--platform={PLATFORM}",
        *channels_args,
        *specs,
    ]
    if verbose:
        cmd.append("-vvv")

    print(">>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--root-prefix", required=True, type=Path, help="Root prefix (env lands at <root-prefix>/envs/xeus-kernels)"
    )
    parser.add_argument("--pyproject", required=True, type=Path, help="Path to pyproject.toml")
    parser.add_argument("--extras", nargs="*", default="", help="Optional-dependency groups to include")
    parser.add_argument(
        "--micromamba",
        action="store_true",
        help="Use a direct micromamba create call instead of jupyterlite_xeus.create_conda_env",
    )
    args = parser.parse_args()

    with open(args.pyproject, "rb") as f:
        proj = tomllib.load(f)["project"]

    spec_by_name = collect_specs(proj, args.extras, base_line_spec=XEUS_RUNTIME)
    specs = list(spec_by_name.values())
    print(specs)
    if args.micromamba:
        create_conda_env_from_specs_micromamba(
            env_name=ENV_NAME,
            root_prefix=args.root_prefix,
            specs=specs,
            channels=XEUS_CHANNELS,
            verbose=True,
        )
    else:
        create_conda_env_from_specs(
            env_name=ENV_NAME,
            root_prefix=args.root_prefix,
            specs=specs,
            channels=XEUS_CHANNELS,
        )


if __name__ == "__main__":
    main()
