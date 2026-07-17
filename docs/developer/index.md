# Developer notes

## Setup a Notebook Python environment

```shell
uv pip install -e '.[dev,docs,lab]'
```

Also install `micromamba`.

To use JupyterLab, you will need a `ipykernel`:

```shell
prefix=$(python -c "import sys; print(sys.prefix)")
jupyter kernelspec uninstall search_demo
python -m ipykernel install --prefix $prefix --name search_demo --display-name "search demo"
```

## Build the docs

To build the Sphinx docs locally, you need to create the JupyterLite sites first:

```shell
jupyterlite_build/xeus.sh
```

And then inject the docs:

```shell
sphinx-build -b html docs/ workspace/public/docs
```

The HTML output is written to `workspace/public/docs/index.html`.

To preview it locally:

```shell
python -m http.server 8000 --directory workspace/public
```

Then open `http://localhost:8000/docs/`.

## JupyterLite

[JupyterLite](https://jupyterlite.readthedocs.io/en/latest/) is a Jupyter distribution that runs entirely in the browser.
Python kernels run client-side, either using the Pyodide-based default kernel or, when the `jupyterlite-xeus` extension is enabled, using a `xeus-python` WebAssembly kernel.

### JupyterLite xeus UI

The notebooks UI is brought by the `--apps notebooks` option of `jupyter lite build`. It is necessary that the venv in which that command is run
does not contain the `notebooks` python package. JupyterLite’s own docs make clear that supported Notebook/JupyterLab versions are tied to the jupyterlite-core release line.

In order to be able to use the "File->Open" menu of the Notebooks UI, one needs to add the app `tree` to the build command.

### JupyterLite Xeus notes for CI

- Channels currently used are `environment.yml`:
  - `https://conda.anaconda.org/conda-forge`
  - `https://repo.prefix.dev/emscripten-forge-dev`
- Keep following xeus dependencies to avoid solver drift and to keep notebook compatibility:
  - `xeus-python`, `xeus-python-shell`, `xeus-python-shell-lite`
  - `ipywidgets`, `ipyleaflet`,`orjson`, `pycparser`, `yarl`, `shapely`, `flexpolyline`
- `pycparser` is expected to come from conda-forge as a noarch package (`pyh...` build string), while `orjson` is expected 
from `emscripten-forge-dev` (e.g. wasm build `3.11.3`).
- If CI fails with `Could not solve for environment specs` mentioning `pycparser` or `xeus-python-shell-lite`, 
verify the specs send to `micromamba` first. You can use the `--micromamba` option of `create_env.py` (in `xeus.sh`)
- Application code remains injectable per commit through:
  - `--XeusAddon.mounts="$ROOT_DIR/src/here_search_demo:/lib/python3.13/site-packages/here_search_demo"`.
- `emscripten-forge` provides conda-style packages for WebAssembly (`emscripten-wasm32`), enabling Python and scientific 
stacks in the browser. Delivery channels:

  | | `emscripten-forge-4x` | `emscripten-forge-dev` |
  |--|--|--|
  | Stability (intended) | higher | lower |
  | Updates | slower | faster |
  | Fix availability | delayed | immediate |

  - when very accurate routes are needed, we use the `pyproj` package.
  `pyproj`  build `_2` in `emscripten-forge-4x` preventing us to use this channel. This needs to be reported. 
  The build in `emscripten-forge-dev` is working, so we can use that channel for now.
  Root cause: broken PROJ data bundle → `Transformer.from_crs` fails


## Inject a lat/lon using geojs.io


`here-search-demo` facilitates the use of the services from [geojs.io][2] to discover the location behind an IP address.
The `get_lat_lon` helper is not used in the demo widgets. If you need to inject the geolocation associated with 
your IP, please check the [GeoJS Terms Of Service][3].


   ```
   from here_search_demo.util import get_lat_lon
   latitude, longitude = await get_lat_lon()
   ```

## Python 3.14 & 3.15

`here-search-demo` can be used in JupyterLab running Python 3.14 or 3.15 JupyterLab. Notebooks on Python 3.15 are very slow at the time of writing (25/6/2026).
Jupyter Xeus isnot supported by the `emscripten-forge` recipe for Python 3.14 or 3.15 yet.:
emscripten-forge [recipe](https://github.com/emscripten-forge/recipes/blob/main/recipes/recipes_emscripten/python/recipe.yaml) for python is currently at 3.13.1, not 3.14.

If Xeus support for Python 3.14 is enabled (see recipe), the `--XeusAddon.mounts` option of `jupyterlite_build/xeus.sh` needs 
to be updated to point to the correct site-packages path.

```shell
brew upgrade pyenv
pyenv install --list | grep 3.15
```

## Shell script checks

Use these commands from the repository root for shell script quality checks in `scripts/*.sh`.

Required tools:
- `shfmt`
- `shellcheck`
- `bashate`

Install on macOS:

```shell
brew install shfmt shellcheck
uv tool install bashate
```

Auto-fix formatting, then run linters:

```shell
shfmt -w jupyterlite_build/*.sh && shellcheck jupyterlite_build/*.sh && bashate -i E002,E003,E006 jupyterlite_build/*.sh
```

Check-only mode (no formatting changes):

```shell
shellcheck jupyterlite_build/*.sh && shfmt -d jupyterlite_build/*.sh && bashate -i E002,E003,E006 jupyterlite_build/*.sh
```

## Update the package


1. Create a release branch from `main`, for example `git checkout -b release/<version>`.
2. Make the code/doc/notebook changes that the new release requires (bug fixes, dependency updates, README notes, etc.), then commit and push those updates so they land on the release branch.
3. Run `bumpver update --set-version <version>` on that branch. The command will update `pyproject.toml`, `README.md`, `src/here_search_demo/__init__.py`, create the version commit, tag it, and push to the remote.
4. Open a PR from your release branch.
5. Ensure the PR’s `test.yml` jobs finish green and that Codecov still reports data for the repo (https://app.codecov.io/gh/heremaps/here-search-demo).
6. After the PR merges into `main`, use “Draft a new release” in GitHub and select the tag created by bumpver.
7. Publishing the release triggers the PyPI workflow and uploads the `here-search-demo-notebooks.zip` asset automatically.



[1]: https://jupyterlite.readthedocs.io/en/latest/howto/configure/storage.html
[2]: https://www.geojs.io/
[3]: https://www.geojs.io/tos/
