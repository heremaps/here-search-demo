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

patch_wheel() {
    local package_name=$1
    local directory=$2
    local wheel_file=$(find "$directory" -name "${package_name}-*.whl" | sort -V | tail -n 1)
    local temp_dir=$(mktemp -d)

    wheel unpack "$wheel_file" -d "$temp_dir"
    sed -i.bak '/Requires/d' "$(find "$temp_dir" -name METADATA)"
    wheel pack "$(dirname "$(find "$temp_dir" -name "*.dist-info")")" -d $directory

    rm -rf "$temp_dir"
}

printf "${YELLOW}Build workspace${NC}\n"
rm -rf workspace
mkdir -p workspace/content-xeus workspace/content-pyodide

if command -v uv &> /dev/null; then
  pip_cmd="uv pip"
else
  pip_cmd="pip"
  python -m pip -q install --upgrade pip
fi

printf "${YELLOW}Create venv-xeus${NC}\n"
pushd workspace
python -m venv venv-xeus
source venv-xeus/bin/activate

printf "${YELLOW}Install jupyter/xeus packages:${NC}\n"
$pip_cmd install jupyter_server jupyterlite-core jupyterlite-xeus libarchive-c

printf "${YELLOW}Copy static content for jupyterlite-xeus site${NC}\n"
cp "$NOTEBOOKS_DIR"/obm*.ipynb content-xeus/
cp "$NOTEBOOKS_DIR"/demo.ipynb content-xeus/
cp "$ROOT_DIR/demo-config-example.json" content-xeus/demo-config.json

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
printf "${YELLOW}Create venv-pyodide${NC}\n"
python -m venv venv-pyodide
source venv-pyodide/bin/activate

printf "${YELLOW}Install jupyter/pyodide packages:${NC}\n"
# https://pyodide.org/en/stable/usage/packages-in-pyodide.html
$pip_cmd install build \
  -e '..[route]' \
  jupyter_server jupyterlab_server jupyterlite-core jupyterlite-pyodide-kernel libarchive-c \
  "orjson==3.10.16" "shapely==2.0.7"

printf "${YELLOW}Build here-search-demo wheel${NC}\n"
python -m build "$ROOT_DIR" --wheel --outdir content-pyodide --skip-dependency-check

printf "${YELLOW}Copy static content for jupyterlite-pyodide site${NC}\n"
echo "{\"ContentsManager\": {\"allow_hidden\": true}}" > jupyter_lite_config.json
cp content-xeus/demo.ipynb content-xeus/obm_{1,2,3}*.ipynb content-pyodide
cat << EOP | python
from importlib import import_module
from importlib.metadata import version
PKGS = ["here_search_demo", "ipyleaflet", "flexpolyline", "ipywidgets", "orjson", "pyproj", "shapely", "xyzservices", "yarl"]
pkgs = ", ".join(
    f'"emfs:{n}-{version(n)}-py3-none-any.whl"'
    if n.startswith("here_")
    else f'"{n}=={version(n)}"'
    for n in PKGS
)
with open("content-pyodide/install.py", "wt") as f:
    f.write("import piplite\nasync def _():\n"
        f"  packages = [{pkgs}]\n"   # <- now {pkgs} is evaluated
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
cp content-xeus/demo-config.json content-pyodide/demo-config.json

ls -l content-pyodide

jupyter lite build \
    --contents content-pyodide \
    --output-dir public/pyodide \
    --lite-dir public/pyodide

deactivate
popd

printf "${YELLOW}Done${NC}\n"
cat << eof
To access the jupyterlite sites, run the following command:
(cd workspace/public; python -m http.server 8000 2>/dev/null)
and navigate to
- http://localhost:8000/ for the jupyterlite-xeus site
- http://localhost:8000/pyodide/ for the jupyterlite-pyodide site
eof

