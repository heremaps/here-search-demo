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
ROOT_DIR="$SCRIPT_DIR"/../../../..
NOTEBOOKS_DIR="$SCRIPT_DIR"/../notebooks
RED='\033[0;31m'
YELLOW='\033[33m'
NC='\033[0m'

serve=1
while getopts n option
do
    case $option in
            (n) serve=0;;
            (*) exit;;
    esac
done

printf "${YELLOW}Build workspace${NC}\n"
rm -rf workspace
mkdir -p workspace/content

printf "${YELLOW}Create venv${NC}\n"
pushd workspace
python -m venv venv
source venv/bin/activate

printf "${YELLOW}Install packages:${NC}\n"
cat "$ROOT_DIR"/requirements/lite.txt
if command -v uv &> /dev/null; then
  uv pip install -r "$ROOT_DIR"/requirements/build.txt
  uv pip install wheel build
else
  python -m pip -q install --upgrade pip
  pip install -r "$ROOT_DIR"/requirements/build.txt
  pip install wheel build
fi

printf "${YELLOW}Build here-search-demo wheel${NC}\n"
#pip wheel -e .. --src .. --wheel-dir content --no-deps --no-binary ":all:"
python -m build "$ROOT_DIR" --wheel --outdir content --skip-dependency-check
wheel unpack "$(find content -name '*.whl')" -d package
sed -i.bak '/Requires/d' "$(find package -name METADATA)"
wheel pack "$(dirname "$(find package -name "*.dist-info")")" -d content
ls -l content

printf "${YELLOW}Build Jupyter Lite static page${NC}\n"
cat << eof > jupyter_lite_config.json
{
  "ContentsManager": {
    "allow_hidden": true
  }
}
eof

cp "$NOTEBOOKS_DIR"/obm*.ipynb content/
cp "$NOTEBOOKS_DIR"/_install.py content/

cp "$NOTEBOOKS_DIR"/demo.ipynb content/demo.ipynb

cp "$ROOT_DIR"/demo-config-example.json content/demo-config.json

jupyter lite build --contents content --output-dir public --lite-dir public

if [ $serve -eq 1 ]; then
    printf "${YELLOW}Serve....${NC}\n"
    jupyter lite serve --lite-dir public
fi
popd
