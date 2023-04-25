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

serve=1
while getopts n option
do
    case $option in
            (n) serve=0;;
            (*) exit;;
    esac
done

rm -rf workspace
mkdir -p workspace/content
(cd workspace
 python -m venv venv
 source venv/bin/activate
 python -m pip -q install --upgrade pip
 pip install -r "$ROOT_DIR"/requirements/util.txt
 pip install -r "$ROOT_DIR"/requirements/lite_run.txt
 #pip wheel -e .. --src .. --wheel-dir content --no-deps --no-binary ":all:"
 python -m build "$ROOT_DIR" --wheel --outdir content --skip-dependency-check
 wheel unpack "$(find content -name '*.whl')" -d package
 sed -i.bak '/Requires/d' "$(find package -name METADATA)"
 wheel pack "$(dirname "$(find package -name "*.dist-info")")" -d content
 cp "$NOTEBOOKS_DIR"/*.ipynb content/
 jupyter lite build --contents content --output-dir public --lite-dir public
 [ $serve -eq 1 ] && jupyter lite serve --lite-dir public
)