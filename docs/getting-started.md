---
hide-toc: true
---

# Getting Started

Three ways to run the demo, from zero-install to full contributor setup.

## 1. Try it online (no install)

- **App only:** open the hosted Voici dashboard from the project README badge.
- **Interactive notebooks:** open the hosted JupyterLite site, then head to
  [Interactive Notebooks](tutorials/index.md) to run them in the browser.

In either case, click the top-right 🔑 on the map to upload a HERE
`credentials.properties` file. See [Credentials](explanation/credentials.md) for
what the file must contain and how it is used.

## 2. Run notebooks locally

1. Install the package into a virtual environment (Python 3.13 recommended):
   ```shell
   pip install 'here-search-demo[lab]' \
     --index-url https://artifactory.in.here.com/artifactory/api/pypi/here-elm-pypi-virtual-prd/simple
   ```
2. Extract the notebooks and `credentials.properties.txt` from `here-search-demo.zip`
   into the same directory.
3. Fill `credentials.properties.txt` with your
   [HERE credentials](https://docs.here.com/geocoding-and-search/docs/get-credentials-ols).
4. Register a Jupyter kernel for the package:
   ```shell
   prefix=$(python -c "import sys; print(sys.prefix)")
   python -m ipykernel install --prefix $prefix --name search_demo --display-name "search demo"
   ```
5. Start JupyterLab:
   ```shell
   python -m jupyterlab
   ```

## 3. Provide credentials

The demo needs two things for the full experience:

- an **API key** (HERE map tiles), and
- **OAuth2 credentials** (authorizing Search / Routing API requests).

Set them via environment variables or a `credentials.properties` file before
launching, or upload the file at runtime through the 🔑 widget. The exact keys,
resolution order, and what degrades when one is missing are documented in
[Credentials](explanation/credentials.md).

## Where to next

- [Tutorials](tutorials/index.md) — run the demo notebooks step by step.
- [Guides](guides/index.md) — task-focused how-tos (search along a route, signals).
- [Explanation](explanation/index.md) — how the engine, routes, and credentials work.
- [Reference](reference/index.md) — the generated API surface and math appendices.
- [Contributing](contributing/index.md) — local dev setup, build internals, releases.
