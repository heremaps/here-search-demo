## Developer notes

### Setup a Notebook Python environment

It is recommended to use a Python virtual environment. In that environment, after a `pip install -e '.[lab]'`, 
you will need to install a kernel. For instance with a:

   ```
   python -m ipykernel install \
      --prefix $(python -c "import sys; print(sys.prefix)") \
      --name search_demo --display-name "search demo"
   ```
   
To run the notebook on Jupyter Classic, you will need:


   ```
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   ```

### Versioning

To update the package version, use `bumpver`. For instance:

   ```
   bumpver update --patch --dry 
   
   INFO    - fetching tags from remote (to turn off use: -n / --no-fetch)
   INFO    - Latest version from VCS tag: 0.9.0
   INFO    - Working dir version        : 0.9.0
   INFO    - Old Version: 0.9.0
   INFO    - New Version: 0.9.1
   --- docs/developers.md
   +++ docs/developers.md
   @@ -56,7 +56,7 @@
       ```
       try:
          import piplite
   -      await piplite.install(["ipywidgets==8.1.0", "ipyleaflet==0.17.3", "emfs:here_search_demo-0.9.5-py3-none-any.whl"], keep_going=True)
   +      await piplite.install(["ipywidgets==8.1.0", "ipyleaflet==0.17.3", "emfs:here_search_demo-0.9.5-py3-none-any.whl"], keep_going=True)
       except ImportError:
          pass
       ```
   (...)
   ```

Push your change through a branch PR. 
Then on your local main branch, after a rebase from origin, do a `bumpver update --patch`.
Finally, "Draft a new release" and choose the new tag you just created with `bumpver`. 
The creation of a new release should trigger the release to pypi workflow.


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
   ```

### JupyterLite

[JupyterLite](https://JupyterLite.readthedocs.io/en/latest/) is a JupyterLab distribution that runs entirely in the browser.
The Python kernels are backed by [`Pyodide`](https://pyodide.org/en/stable/) running in a Web Worker.

Pyodide can not be used outside a browser. But for development purposes (type hints), it is advised to
install its [`py`](https://github.com/pyodide/pyodide/tree/main/src/py) package into the venv used for `here-search-demo`.

   ```
   git clone git@github.com:pyodide/pyodide.git
   cd pyodide/src/py
   pip install -e .
   ```

For the Pyodide kernels to be able to use certain packages, those need to be installed from the notebook itself:

   ```
   try:
      import piplite
      await piplite.install(["ipywidgets==8.1.0", "ipyleaflet==0.17.3", "emfs:here_search_demo-0.9.5-py3-none-any.whl"], keep_going=True)
   except ImportError:
      pass
   ```

The version of `here_search_demo` in the `.ipynb` files and this `developers.md` is updated through `bumpver`.

#### From a local git clone

To test the JupyterLite page locally, run from the local git repository:

   ```
   $(find . -name "lite-run.sh")
   ```

Option `-n` only builds the page and does not serve it. 

#### Without git clone

To test the JupyterLite page locally, run in a virtualenv :

   ```
   pip download here-search-demo --no-deps --no-binary ":all:"
   
   tar xpfz $(find . -name "*.tar.gz")
   
   $(find src -name "lite-run.sh")
   ```

#### Clear your browser cache

By default, JupyterLite uses the [browser storage][1] to store settings and site preferences. 
It is sometimes helpful to clear in the browser settings the `127.0.0.1` site data to not use a stale state. 


### Inject a lat/lon using geojs.io


`here-search-demo` facilitates the use of the services from [geojs.io][2] to discover the location behind an IP address.
The `get_lat_lon` helper is not used in the demo widgets. If you need to inject the geolocation associated with 
your IP, please check the [GeoJS Terms Of Service][3].


   ```
   from here_search.demo.util import get_lat_lon
   latitude, longitude = await get_lat_lon()
   ```

[1]: https://jupyterlite.readthedocs.io/en/latest/howto/configure/storage.html
[2]: https://www.geojs.io/
[3]: https://www.geojs.io/tos/