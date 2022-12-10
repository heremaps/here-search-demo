#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

rm -rf content public _output build dist
mkdir content

rm -rf venv
python -m venv venv
(source venv/bin/activate
 python -m pip install --upgrade pip
 pip install jupyterlab jupyterlab_widgets jupyterlab-filesystem-access jupyterlite ipywidgets==7.7.2 ipyleaflet==0.17.1 wheel
 pip -v wheel ".[lite]" --wheel-dir content --no-deps --no-binary ":all:"
 cp $SCRIPT_DIR/../notebooks/*.ipynb content/

 jupyter lite build --contents content --output-dir public --lite-dir public
 jupyter lite serve --lite-dir public
)