---
hide-toc: true
---

# Build infrastructure

Deeper notes on the browser-runtime build stack (JupyterLite, xeus, Voici), CI
solver constraints, and Python-version support.

## JupyterLite

[JupyterLite](https://jupyterlite.readthedocs.io/en/latest/) is a Jupyter distribution that runs entirely in the browser.
Python kernels run client-side, either using the Pyodide-based default kernel or, when the `jupyterlite-xeus` extension is enabled, using a `xeus-python` WebAssembly kernel.

### JupyterLite xeus UI

The notebooks UI is brought by the `--apps notebooks` option of `jupyter lite build`. It is necessary that the venv in which that command is run
does not contain the `notebooks` python package. JupyterLite’s own docs make clear that supported Notebook/JupyterLab versions are tied to the jupyterlite-core release line.

In order to be able to use the "File->Open" menu of the Notebooks UI, one needs to add the app `tree` to the build command.

### JupyterLite Xeus notes for CI

- CI runs on GitLab `docker-autoscaler` using `python:3.11` x86_64.
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

## Voici

Voici reuses the same xeus kernel stack, but it builds an app-style dashboard output instead of the full JupyterLite shell.
It is built by the same script and command path as JupyterLite:

```shell
jupyterlite_build/xeus.sh
```

This sheel script builds:
- the xeus JupyterLite lab & notebooks site under `workspace/`
- the xeus Voici app for `notebooks/basic-demo.ipynb` under `workspace/voici/`

By default, JupyterLite uses the [browser storage][1] to store settings and site preferences. 
It is sometimes helpful to clear in the browser settings the `127.0.0.1` site data to not use a stale state. 

Reference: 
- https://jupyterlite.readthedocs.io/en/stable/
- https://emscripten-forge.org/blog/
- https://xeus-python-kernel.readthedocs.io/en/latest/

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

[1]: https://jupyterlite.readthedocs.io/en/latest/howto/configure/storage.html
