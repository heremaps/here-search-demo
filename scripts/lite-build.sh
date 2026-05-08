#!/bin/bash

###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ROOT_DIR="$SCRIPT_DIR"/..
NOTEBOOKS_DIR="$SCRIPT_DIR"/../notebooks
TAR_CMD=$(command -v gtar || echo "tar")
RED='\033[0;31m'
YELLOW='\033[33m'
NC='\033[0m'

printf "${YELLOW}Build workspace${NC}\n"
rm -rf workspace
mkdir -p workspace/content-xeus workspace/content-pyodide

if command -v uv &> /dev/null; then
  pip_cmd="uv pip"
else
  pip_cmd="pip"
  python -m pip -q install --upgrade pip
fi

add_credentials_file () {
    local directory=$1
    cat <<EOF >$directory/credentials.properties.txt
here.token.endpoint.url = https://account.api.here.com/oauth2/token
here.access.key.id = ...
here.access.key.secret = ...
here.api.key = ...
#here.token.scope = ...
EOF
}

process_for_xeus() {
    printf "${YELLOW}Create venv-xeus${NC}\n"
    pushd workspace
    mkdir -p content-xeus
    python -m venv venv-xeus
    source venv-xeus/bin/activate

    printf "${YELLOW}Install jupyter/xeus packages:${NC}\n"
    $pip_cmd install jupyter_server jupyterlite-core jupyterlite-xeus libarchive-c

    printf "${YELLOW}Copy static content for jupyterlite-xeus site${NC}\n"
    cp "$NOTEBOOKS_DIR"/obm*.ipynb content-xeus/
    # Use gl-demo.ipynb internally, demo.ipynb on github
    # cp "$NOTEBOOKS_DIR"/demo.ipynb content-xeus/
    cp "$NOTEBOOKS_DIR"/gl-demo.ipynb content-xeus/demo.ipynb
    add_credentials_file content-xeus
    ls -l content-xeus

    cat << eof > environment.yml
name: xeus-kernels
channels:
  - https://prefix.dev/emscripten-forge-dev
  - https://prefix.dev/conda-forge
dependencies:
  - xeus-python
  - ipywidgets
  - ipyleaflet
  - orjson
  - yarl
  - xyzservices>=2025.11.0
  - shapely
  - pyproj
  - flexpolyline

eof

    jupyter lite build \
        --contents content-xeus \
        --output-dir public \
        --XeusAddon.environment_file=$(pwd)/environment.yml \
        --XeusAddon.mount_jupyterlite_content=True \
        --XeusAddon.mounts="$ROOT_DIR/src/here_search_demo:/lib/python3.13/site-packages/here_search_demo"

    deactivate
    popd
}

process_for_pyodide() {
    printf "${YELLOW}Create venv-pyodide${NC}\n"
    pushd workspace
    mkdir -p content-pyodide
    python -m venv venv-pyodide
    source venv-pyodide/bin/activate

    printf "${YELLOW}Install jupyter/pyodide packages:${NC}\n"
    # https://pyodide.org/en/stable/usage/packages-in-pyodide.html
    $pip_cmd install build \
      -e '..[route]' \
      jupyter_server jupyterlab_server jupyterlite-core jupyterlite-pyodide-kernel libarchive-c

    printf "${YELLOW}Build here-search-demo wheel${NC}\n"
    python -m build "$ROOT_DIR" --wheel --outdir content-pyodide --skip-dependency-check

    printf "${YELLOW}Copy static content for jupyterlite-pyodide site${NC}\n"
    cp "$NOTEBOOKS_DIR"/obm*.ipynb content-pyodide/
    cp "$NOTEBOOKS_DIR"/demo.ipynb content-pyodide/
    add_credentials_file content-pyodide
    cat << EOP | python
import re, tomllib
from importlib.metadata import version
proj = tomllib.load(open("$ROOT_DIR/pyproject.toml", "rb"))
def pkg_name(dep):
    return re.split(r"[>=<!;\[ ]", dep)[0].strip()
exclude = {"aiohttp"}  # replaced by pyfetch on emscripten
deps = proj["project"]["dependencies"]
route_deps = proj["project"]["optional-dependencies"]["route"]
pkgs = [pkg_name(d) for d in deps + route_deps if pkg_name(d) not in exclude]

v = version("here_search_demo")
pkg_list = f'"emfs:here_search_demo-{v}-py3-none-any.whl", ' + ", ".join(f'"{p}"' for p in pkgs)
with open("content-pyodide/install.py", "wt") as f:
    f.write(f"import piplite\nasync def _():\n"
        f"  packages = [{pkg_list}]\n"
        "  await piplite.install(packages, keep_going=True)\n")
EOP
    cat content-pyodide/install.py

    # Add a pyodide pipeline related install line
    if ! command -v jq &> /dev/null; then
        printf "${RED}jq is required to patch the notebooks${NC}\n"
        exit 1
    fi
    for nb in content-pyodide/demo.ipynb content-pyodide/obm*.ipynb; do
        [ -f "$nb" ] || continue
        jq '
            .cells |= map(
            if .cell_type == "code" then
                .source |= ["from install import _; await _()\n"] + .
            else
                .
            end)
        ' "$nb" > notebook.tmp && mv notebook.tmp "$nb"
    done

    ls -l content-pyodide

    jupyter lite build \
        --contents content-pyodide \
        --output-dir public/pyodide \
        --lite-dir public/pyodide

    deactivate
    popd
}

process_for_xeus
process_for_pyodide

printf "${YELLOW}Done${NC}\n"
cat << eof
To access the jupyterlite sites, run the following command:
(cd workspace/public; python -m http.server 8000 2>/dev/null)
and navigate to
- http://localhost:8000/ for the jupyterlite-xeus site
- http://localhost:8000/pyodide/ for the jupyterlite-pyodide site
eof

