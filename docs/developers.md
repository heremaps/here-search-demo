## Developer notes

### Setup a Notebook Python environment

It is recommended to use a Python virtual environment. In that environment, after a `pip install -e '.[lab,route]'`, 
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
Python kernels run client-side, either using the Pyodide-based default kernel or, when the `jupyterlite-xeus` extension is enabled, using a `xeus-python` WebAssembly kernel.


To test the jupyterlite page locally, run from the local git repository:

   ```shell
   scripts/lite-build.sh
   ```

By default, JupyterLite uses the [browser storage][1] to store settings and site preferences. 
It is sometimes helpful to clear in the browser settings the `127.0.0.1` site data to not use a stale state. 

Reference: 
- https://jupyterlite.readthedocs.io/en/stable/
- https://emscripten-forge.org/blog/
- https://xeus-python-kernel.readthedocs.io/en/latest/


### Inject a lat/lon using geojs.io


`here-search-demo` facilitates the use of the services from [geojs.io][2] to discover the location behind an IP address.
The `get_lat_lon` helper is not used in the demo widgets. If you need to inject the geolocation associated with 
your IP, please check the [GeoJS Terms Of Service][3].


   ```
   from here_search_demo.util import get_lat_lon
   latitude, longitude = await get_lat_lon()
   ```

### Python 3.14

`here-search-demo` is supporting Python 3.14 on JupyterLab, but not on jupyter-xeus:
emscripten-forge [recipe](https://github.com/emscripten-forge/recipes/blob/main/recipes/recipes_emscripten/python/recipe.yaml) for python is currently at 3.13.1, not 3.14

### Python 3.15

Python 3.15 is interesting because of its async profiler. At the time of writing (11/3/2026), 
following packages were not available on Python 3.15 (`3.15.0a8`): 
- `rdps-py` needed by the `lab` extra (actually by the `jupyterlab` package)
- `pyproj` needed by the `route` extra

### Update the package

1. Create a release branch from `main`, for example `git checkout -b release/<version>`.
2. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
3. Run `bumpver update --set-version <version>` on that branch. The command will update `pyproject.toml` and `src/here_search_demo/__init__.py`, create the version commit, tag it, and push to the remote.
4. Open a PR from your release branch.
5. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
6. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
7. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.



[1]: https://jupyterlite.readthedocs.io/en/latest/howto/configure/storage.html
[2]: https://www.geojs.io/
[3]: https://www.geojs.io/tos/