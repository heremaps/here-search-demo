[![Python package][6]][7]
[![codecov][8]][9]
[![xeus-badge][10]][3]
[![pyodide-badge][10b]][3b]


# HERE Search notebooks

A set of widgets and notebooks demonstrating the use of [HERE Geocoding & Search][4] endpoints `/autosuggest`,  `/discover`, `/browse`, and `/lookup`.

![searching for pizza][11]

Requirements: a [HERE API key][1] and a Python environment. Note that HERE Base Plan [Pricing][5] allows you to get started for free.

| Use Case            | Installation                                          |
|:--------------------|:------------------------------------------------------|
| Online use          | Run the notebooks [in your browser][3]                |
| Local use           | [Install and try locally](#install-and-try-locally)   |
| Package maintenance | [Install from the sources](#install-from-the-sources) |

## 0-install use

`here-search-demo` notebooks are available for immediate use in a [Github page][3] hosting a JupyterLite instance based on the `xeus` stack (CPython running on `xeus-python` kernel). 

A version of these pages based on the Pyodide stack and the `jupyterlite-pyodide-kernel` is also available [here][3b]. 

## Install and try locally

If you want to use the library and try it through existing notebooks, do:

1. Install the widgets:
   ```shell
   uv pip install 'here-search-demo[lab,route]'
   ```
   
2. Grab the notebooks from the [GitHub release asset][12]
3. Add your [HERE API key][1] to `demo-config.json` file.

## Install from the sources

If you need to maintain this package:

1. `git clone` it and into a `virtualenv`/`venv`, do:
   ```shell
   uv pip install -e '.[dev,lab,route]'
   ```

2. Copy `example-credentials.properties` to `notebooks/credentials.properties` and update the later one with your [HERE credentials][1].

3. Link the virtual environment to a IPython kernel:

   ```shell
   python -m ipykernel install \
     --prefix $(python -c "import sys; print(sys.prefix)") \
     --name search_demo --display-name "search demo"
   ```

4. Start either

     - JupyterLab:
       ```shell
       python -m jupyterlab notebooks
       ```
     - or JupyterLite
       ```shell
       bash scripts/lite-build.sh
       ```



(Additional [notes][2])

## License

Copyright (C) 2022-2026 HERE Europe B.V.

This project is licensed under the MIT license - see the [LICENSE](./LICENSE) file in the root of this project for license details.

[1]: https://www.here.com/docs/bundle/geocoding-and-search-api-developer-guide/page/topics/quick-start.html#get-an-api-key
[2]: https://github.com/heremaps/here-search-demo/blob/main/docs/developers.md
[3]: https://heremaps.github.io/here-search-demo/lab/?path=demo.ipynb
[3b]: https://heremaps.github.io/here-search-demo/pyodide/lab/?path=demo.ipynb
[4]: https://www.here.com/docs/category/geocoding-search-v7
[5]: https://www.here.com/get-started/pricing

[6]: https://github.com/heremaps/here-search-demo/actions/workflows/test.yml/badge.svg
[7]: https://github.com/heremaps/here-search-demo/actions/workflows/test.yml
[8]: https://codecov.io/gh/heremaps/here-search-demo/branch/main/graph/badge.svg?token=MVFCS4BUFN
[9]: https://codecov.io/gh/heremaps/here-search-demo
[11]: https://github.com/heremaps/here-search-demo/raw/main/docs/screenshot.jpg
[10]: https://img.shields.io/badge/try-lite%20now-f7dc1e.svg?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0Ni43IDQ2LjciPgogIDxwYXRoCiAgICBmaWxsPSIjNDBCM0MzIgogICAgZD0iTTUgMGMyLjUuOCA0LjUgMiA0LjYgMi4xIDEuOSAxLjMgMy42IDMuMSA0LjggNS4xLjQuNiA1LjIgNy44IDguNiAxMi45LS44IDEuMi0xLjUgMi4zLTIuMSAzLjEgMC0uMS0uMS0uMS0uMS0uMkMxNy42IDE3LjkgMTEuNCA4LjYgMTEgNy45Yy0uOS0xLjMtMi0yLjUtMy41LTMuNCAwIDAtMS41LTEtMy41LTEuNkMzLjIgMi42IDEuOCAyLjQgMCAyLjJ2NDIuNGMxLjgtLjIgMy4yLS40IDQtLjcgMi0uNiAzLjUtMS42IDMuNS0xLjYgMS41LTEgMi43LTIuMiAzLjUtMy40LjQtLjcgNi42LTkuOSAxMC4xLTE1LjJDMjQgMTkuMSAzMS40IDguMSAzMS45IDcuM2MxLjItMiAyLjktMy44IDQuOC01LjEgMC0uMSAyLjEtMS4zIDQuNi0yLjFMNDEuOCAwSDV6CiAgICAgICBNNDYuNyAyLjJjLTEuOC4yLTMuMi40LTQgLjctMi4xLjYtMy42IDEuNi0zLjYgMS42LTEuNS45LTIuNiAyLjEtMy41IDMuNC0uNC43LTYuNiA5LjktMTAuMSAxNS4yLTIuOSA0LjQtMTAuMyAxNS41LTEwLjggMTYuMi0xLjIgMi0yLjkgMy44LTQuOCA1LjEgMCAuMS0yLjEgMS4zLTQuNiAyLjFsLS41LjFoMzYuOGwtLjQtLjFjLTIuNS0uOC00LjUtMi00LjYtMi4xLTEuOS0xLjMtMy42LTMuMS00LjgtNS4xLS40LS42LTUuMi03LjgtOC42LTEyLjkuOC0xLjIgMS41LTIuMyAyLjEtMy4xIDAgLjEuMS4xLjEuMiAzLjUgNS4zIDkuNyAxNC41IDEwLjEgMTUuMi45IDEuMyAyIDIuNSAzLjUgMy40IDAgMCAxLjUgMSAzLjUgMS42LjguMyAyLjIuNSA0IC43VjIuMnoiCiAgLz4KPC9zdmc+Cgo=
[10b]: https://jupyterlite.rtfd.io/en/latest/_static/badge.svg
[12]: https://github.com/heremaps/here-search-demo/releases/latest/download/here-search-demo-notebooks.zip
