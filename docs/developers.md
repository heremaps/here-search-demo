## Developer notes

### Setup a Notebook Python environment

It is recommended to use a Python virtual environment. The below recipe uses the python batteries `venv` module.
It has only been tested on a Macos Monterey machine, but it should not be too difficult to use it on another Unix-like workstation.

1. Virtual environment

   ```
   mkdir -p ~/virtualenv; (cd ~/virtualenv; python -m venv search-notebook)
   source ~/virtualenv/search-notebook/bin/activate
   ```

2. Download and install

   For users:

   ```
   pip -v install here-search-demo
   ```

   For contributors/developers:

   ```
   git clone git@github.com:heremaps/here-search-demo.git
   cd search-notebook-ext
   pip install -e .
   ```

3. Jupyter config

   ```
   python -m ipykernel install --user --name search_demo --display-name "search demo"
   ```
   
To run the notebook on Jupyter Classic, you will need:

   ```
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   ```

### Upload a new package to a pypa repository

   ```
   pip install -r requirements/util.txt
   python -m build --sdist --wheel
   twine upload dist/*
   ```

### Test on MacOS / python3.7

1. Build Python 3.7.9 for `pyenv`

   ```
   brew install zlib bzip2 openssl@1.1 readline xz
   CFLAGS="-I$(brew --prefix openssl)/include -I$(brew --prefix bzip2)/include -I$(brew --prefix readline)/include -I$(xcrun --show-sdk-path)/usr/include"
   LDFLAGS="-L$(brew --prefix openssl)/lib -L$(brew --prefix readline)/lib -L$(brew --prefix zlib)/lib -L$(brew --prefix bzip2)/lib"
   pyenv install 3.7.9
   ```

2. Create virtual environment

   ```
   pyenv virtualenv 3.7.9 venv3.7
   pyenv activate venv3.7
   pyenv local venv3.7 && python -V
   pip install -e .
   pip install -r requirements_dev.txt
   ```

### JupyterLite

[JupyterLite](https://jupyterlite.readthedocs.io/en/latest/) is a JupyterLab distribution that runs entirely in the browser.
The Python kernels are backed by [`Pyodide`](https://pyodide.org/en/stable/) running in a Web Worker.

Pyodide can not be used outside a browser. But for development purposes (type hints), it is advised to
install its [`py`](https://github.com/pyodide/pyodide/tree/main/src/py) package into the venv used for `search-notebook-ext`

   ```
   git clone git@github.com:pyodide/pyodide.git
   cd pyodide/src/py
   pip install -e .
   ```

For the Pyodide kernels to be able to use certain packages, those need to be installed from the notebook itself:

   ```
   try:
      import piplite
      await piplite.install(["ipywidgets==7.7.1", "ipyleaflet==0.17.1", "emfs:here_search_widget-0.6.1-py3-none-any.whl"], keep_going=True)
   except ImportError:
      pass
   ```

#### From a local git clone

To test the jupyterlite page locally, run from the local git repository:

   ```
   $(find . -name "lite_run.sh")
   ```

Option `-n` only builds the page and does not serve it. 

A way to get the sources without git cloning the project is to use the source distribution:

   ```
   pip install --upgrade pip
   pip download here-search-demo --no-deps --no-binary ":all:"
   
   tar xpfz $(find . -name "*.tar.gz")
   
   $(find . -name "lite_run.sh")
   ```

## Inject a lat/lon using geojs.io

   ```
   from here_search.demo.util import get_lat_lon
   latitude, longitude = await get_lat_lon()
   ```
