[![Python package][6]][7]
[![codecov][8]][9]
[![jupyterLite-badge][jupyterLite-badge]][3]
[![voici-badge][voici-badge]][3c]


# HERE Search demo

Package version: `0.36.2`

A set of widgets and notebooks demonstrating 
- the use of [HERE Geocoding & Search][4] endpoints `/autosuggest`,  `/discover`, `/browse`, `/lookup` and `/signals`. 
- the integration of [HERE Routing][routing] for search along the route use cases. 


<table>
  <tr>
    <td><img src="https://github.com/heremaps/here-search-demo/raw/main/docs/screenshot_ta.jpg"/></td>
    <td><img src="https://github.com/heremaps/here-search-demo/raw/main/docs/screenshot_fuel.jpg"/></td>
  </tr>
  <tr>
    <td><img width="500" src="https://github.com/heremaps/here-search-demo/raw/main/docs/screenshot_traveltime.jpg"/></td>
    <td/>
  </tr>
</table>

Requirements: [HERE credentials][1] (both API key and OAuth2 key/secret) and a Python environment. Note that HERE Base Plan [Pricing][5] allows you to get started for free.

| I want to...                             | Recommended path                             |
|:-----------------------------------------|:---------------------------------------------|
| Load my creds 🔑and use the app          | [![voici-badge][voici-badge]][3c]            |
| Try online interactive notebooks         | [![jupyterLite-badge][jupyterLite-badge]][3] |
| Use notebooks locally in a Python setup  | [Offline notebooks](#offline-notebooks)      |
| Contribute or run full project workflows | [Contribute](#contribute)                    |

Online documentation with interactive notebooks is available [here][docs].

## Offline notebooks

1. Install the package in the virtual environment of your choice (Python 3.13 recommended):
   ```shell
   pip install 'here-search-demo[lab]'
   ```
2. Extract notebooks and `credentials.properties.txt` from [here-search-demo.zip][12] in to the same directory.
3. Update `credentials.properties.txt` with your [HERE credentials][1].
4. Create a ipykernel for the package:
   ```shell
   prefix=$(python -c "import sys; print(sys.prefix)")
   python -m ipykernel install --prefix $prefix --name search_demo --display-name "search demo"
   ```
4. Start JupyterLab:
   ```shell
   python -m jupyterlab
   ```

## Contribute

1. Clone the repository and install dependencies:
   ```shell
   uv pip install -e '.[dev,docs,lab]'
   ```
   Also install [micromamba][micromamba].
2. Run tests:
   ```shell
   pytest -n auto --ignore=tests/test_notebooks.py
   ```
3. Build the JupyterLite static page:
   ```shell
   jupyterlite_build/xeus.sh
   ```
3b. JupyterLab alternative:
   ```shell
   prefix=$(python -c "import sys; print(sys.prefix)")
   python -m ipykernel install --prefix $prefix --name search_demo --display-name "search demo"
   ```
   Then:
   ```shell
   python -m jupyterlab notebooks
   ``` 
4. Build the docs page:
   ```shell
   sphinx-build -b html docs/ workspace/public/docs
   ```

(Additional [notes][2])

## License

Copyright (C) 2022-2026 HERE Europe B.V.

This project is licensed under the MIT license - see the [LICENSE](./LICENSE) file in the root of this project for license details.

Note: This MIT-licensed project uses only open-source, community-maintained tools—such as **JupyterLite**, **xeus kernels**, **micromamba**, and packages from **conda-forge** and **emscripten-forge-dev**—and includes no Anaconda-distributed components. Each dependency remains under its own open-source license; see their LICENSE files for details.

[1]: https://docs.here.com/geocoding-and-search/docs/get-credentials-ols
[2]: https://github.com/heremaps/here-search-demo/blob/main/docs/contributing/index.md
[3]: https://heremaps.github.io/here-search-demo/lab/?path=demo.ipynb
[3c]: https://heremaps.github.io/here-search-demo/voici/render/basic-demo.html?
[4]: https://docs.here.com/geocoding-and-search/docs/introduction-to-here-geocoding-search-api-v7
[5]: https://www.here.com/get-started/pricing
[routing]: https://docs.here.com/routing/docs/routing-v8-intro
[docs]: https://heremaps.github.io/here-search-demo/docs/index.html

[6]: https://github.com/heremaps/here-search-demo/actions/workflows/test.yml/badge.svg
[7]: https://github.com/heremaps/here-search-demo/actions/workflows/test.yml
[8]: https://codecov.io/gh/heremaps/here-search-demo/branch/main/graph/badge.svg?token=MVFCS4BUFN
[9]: https://codecov.io/gh/heremaps/here-search-demo
[12]: https://github.com/heremaps/here-search-demo/releases/latest/download/here-search-demo-notebooks.zip
[jupyterLite-badge]: https://jupyterlite.rtfd.io/en/latest/_static/badge.svg
[voici-badge]: docs/voici-badge.svg
