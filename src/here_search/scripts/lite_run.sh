#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

rm -rf content public _output build dist venv
python -m venv venv
source venv/bin/activate
mkdir content

pip install jupyterlab jupyterlab_widgets jupyterlite ipywidgets==7.7.2 ipyleaflet==0.17.1 wheel
jupyter nbextension enable --py widgetsnbextension --sys-prefix
jupyter labextension install @jupyterlab/geojson-extension
pip -v wheel ".[lite]" --wheel-dir content --no-deps --no-binary ":all:"
cp $SCRIPT_DIR/../notebooks/*.ipynb content/

jupyter lite build --contents content --output-dir public --lite-dir public
jupyter lite serve --lite-dir public
