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

### JupyterLite

[JupyterLite](https://jupyterlite.readthedocs.io/en/latest/) is a JupyterLab distribution that runs entirely in the browser.
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
      await piplite.install([
          "ipywidgets==...", 
          "ipyleaflet==...", 
          "emfs:here_search_demo-..."], keep_going=True)
   except ImportError:
      pass
   ```

Note that this import is done in `_install.py`.

The version of `here_search_demo` in the `.ipynb` files and this `developers.md` is updated through `bumpver`.

#### From a local git clone

To test the jupyterlite page locally, run from the local git repository:

   ```
   src/here_search/demo/scripts/lite-run.sh
   ```

Option `-n` only builds the page and does not serve it. 

#### Without git clone

To test the JupyterLite page locally, run in a virtualenv :

   ```
   pip download here-search-demo --no-deps --no-binary ":all:"
   
   tar xpfz $(find . -name "*.tar.gz")
   
   src/here_search/demo/scripts/lite-run.sh
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

### Update Jupyter libs

If you need to update Jupyter libis (ipyleaflet, ipywidgets, jupyter*, ...), check following artifacts:
- `developers.md`
- all notebooks
- `requirements/build.txt` and `requirements/lite.txt`

### Update the package

1. Create a release branch from `main`, for example `git checkout -b release/<version>`.
2. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
3. Run `bumpver update --set-version <version>` on that branch so `pyproject.toml`, `_install.py`, and this file are updated together.
4. Commit and push the bump (`git commit -am "bump version …" && git push origin release/<version>`), then open a PR.
5. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
6. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
7. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.



[1]: https://jupyterlite.readthedocs.io/en/latest/howto/configure/storage.html
[2]: https://www.geojs.io/
[3]: https://www.geojs.io/tos/