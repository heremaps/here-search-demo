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

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
ROOT_DIR=$(cd "$SCRIPT_DIR/.." && pwd -P)

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

printf '%b\n' "${YELLOW}Copy & strip notebooks${NC}"
cp -r "$NOTEBOOKS_DIR"/obm*.ipynb "$CONTENT_DIR"/
cp "$NOTEBOOKS_DIR"/demo.ipynb "$CONTENT_DIR"/
python -m jupyterlite_build.strip_notebooks \
	--notebooks-dir "$CONTENT_DIR"

printf '%b\n' "${YELLOW}Create Python environment${NC}"
python -m venv "$WORKSPACE/venv"
# shellcheck source=/dev/null
source "$WORKSPACE/venv/bin/activate"

printf '%b\n' "${YELLOW}Install build dependencies${NC}"
export UV_PROJECT_ENVIRONMENT="$WORKSPACE/venv"
uv sync --only-group xeus_build --no-install-project

printf '%b\n' "${YELLOW}Add credentials${NC}"
cp "$NOTEBOOKS_DIR"/credentials.properties.txt "$CONTENT_DIR"/

printf '%b\n' "${YELLOW}Build Xeus prefix${NC}"
python -m jupyterlite_build.xeus.create_env \
	--root-prefix "$XEUS_ROOT_PREFIX" \
	--pyproject "$ROOT_DIR/pyproject.toml"

printf '%b\n' "${YELLOW}Build JupyterLite site${NC}"
pushd "$WORKSPACE" >/dev/null
jupyter lite build --apps notebooks --apps voici --apps tree --apps edit --apps lab \
	--contents "$CONTENT_DIR"/ \
	--output-dir "$PUBLIC_DIR" \
	--XeusAddon.prefix="$XEUS_KERNELS_DIR" \
	--XeusAddon.mount_jupyterlite_content=True \
	--XeusAddon.mounts="$ROOT_DIR/src/here_search_demo:/lib/python3.13/site-packages/here_search_demo"

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

