#!/usr/bin/env bash
###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

set -e

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

WORKSPACE="$ROOT_DIR/workspace"
XEUS_ROOT_PREFIX="$WORKSPACE/_xeus-prefix-root"
XEUS_KERNELS_DIR="$XEUS_ROOT_PREFIX/envs/xeus-kernels"
PUBLIC_DIR="$WORKSPACE/public"
CONTENT_DIR="$WORKSPACE/content"
NOTEBOOKS_DIR="$ROOT_DIR/notebooks"

RED='\033[31m'
YELLOW='\033[33m'
NC='\033[0m'

printf '%b\n' "${YELLOW}Clean workspace for JupyterLite xeus${NC}"
rm -rf "$WORKSPACE"
mkdir -p "$CONTENT_DIR"

printf '%b\n' "${YELLOW}Copy notebooks${NC}"
mkdir -p "$CONTENT_DIR/route/high_level"
cp "$NOTEBOOKS_DIR"/ch*.ipynb "$CONTENT_DIR"/
cp "$NOTEBOOKS_DIR"/demo.ipynb "$CONTENT_DIR"/demo.ipynb
cp "$NOTEBOOKS_DIR"/basic-demo.ipynb "$CONTENT_DIR"/basic-demo.ipynb
cp "$NOTEBOOKS_DIR"/route/*.ipynb "$CONTENT_DIR"/route/
cp "$NOTEBOOKS_DIR"/route/high_level/*.ipynb "$CONTENT_DIR"/route/high_level/

printf '%b\n' "${YELLOW}Create Python environment${NC}"
# uv venv (not python -m venv): a bare `python` can resolve to a standalone
# build whose ensurepip fails; uv provisions a clean interpreter with pip.
uv venv "$WORKSPACE/venv"
# shellcheck source=/dev/null
source "$WORKSPACE/venv/bin/activate"

printf '%b\n' "${YELLOW}Install build dependencies${NC}"
export UV_PROJECT_ENVIRONMENT="$WORKSPACE/venv"
uv sync --only-group xeus_build --no-install-project

printf '%b\n' "${YELLOW}Strip notebooks${NC}"
# jl-forge notebooks --strip replaces jupyterlite_build.strip_notebooks
# (clears code-cell outputs/execution counts recursively, in place).
jl-forge notebooks "$CONTENT_DIR" --strip

printf '%b\n' "${YELLOW}Add credentials${NC}"
# Jupyter UI on xeus does not render/edit credentials.properties correctly.
# credentials.properties.txt is OK
cp "$NOTEBOOKS_DIR"/credentials.properties.txt "$CONTENT_DIR"/

printf '%b\n' "${YELLOW}Build Xeus prefix${NC}"
# jl-forge xeus-env replaces jupyterlite_build.xeus.create_env; it uses the same
# xeus-python runtime, conda-forge + emscripten-forge-dev channels, platform
# emscripten-wasm32 and env name xeus-kernels, collecting specs from pyproject.
jl-forge xeus-env \
	--root-prefix "$XEUS_ROOT_PREFIX" \
	--pyproject "$ROOT_DIR/pyproject.toml"

# jl-forge xeus-mount derives the in-kernel site-packages path from the Python
# actually installed in the prefix (no hard-coded python3.13), replacing the
# former literal --XeusAddon.mounts value.
MOUNT=$(jl-forge xeus-mount "$ROOT_DIR/src/here_search_demo" --prefix "$XEUS_KERNELS_DIR")

printf '%b\n' "${YELLOW}Build JupyterLite site${NC}"
pushd "$WORKSPACE" >/dev/null
jupyter lite build --apps notebooks --apps voici --apps tree --apps edit --apps lab \
	--contents "$CONTENT_DIR"/ \
	--output-dir "$PUBLIC_DIR" \
	--XeusAddon.prefix="$XEUS_KERNELS_DIR" \
	--XeusAddon.mount_jupyterlite_content=True \
	--XeusAddon.mounts="$MOUNT"

printf '%b\n' "${YELLOW}Reduce site size${NC}"
(
	cd "$PUBLIC_DIR"
	zip -qr - . 2>/dev/null | wc -c | awk '{printf "%.1f MB\n",$1/1024/1024}'
)
find "$PUBLIC_DIR"/build -type f -name '*.js.map' -delete
find "$PUBLIC_DIR/build" -type f -name '*.css.map' -delete
(
	cd "$PUBLIC_DIR"
	zip -qr - . 2>/dev/null | wc -c | awk '{printf "%.1f MB\n",$1/1024/1024}'
)
echo "Top 10 largest packages:"
(
	cd "$PUBLIC_DIR"/
	ls -lS xeus/xeus-kernels/kernel_packages/* | head -10
)

popd >/dev/null
deactivate

echo ""
echo "Serve locally:"
echo "python -m http.server 8000 --directory $PUBLIC_DIR 2>/dev/null"
echo ""
echo "JupyterLab UI:"
echo "http://localhost:8000/lab/"
echo ""
echo "Notebook UI:"
echo "http://localhost:8000/tree/"
echo "http://localhost:8000/notebooks/index.html?path=demo.ipynb"
echo ""
echo "Voici app:"
echo "http://localhost:8000/voici/render/basic-demo.html"
echo ""
