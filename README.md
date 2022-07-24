# Search Notebook

A jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest`,  `/discover`, `/lookup`, `/revgeocode`,  and `/signals`.

![searching for restaurants](screenshot.png)

    
<code>API_KEY="[your api key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key)" here-search-notebook</code>

## Installation

    $ pip -v install here-search-demo --extra-index-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi/simple

### step-by-step

It is recommended to use a virtual environment. The below recipe uses the python batteries `venv` module.
It has only been tested on a macos Monterey machine.

1. Virtual environment

   ```
   $ mkdir -p ~/virtualenv; (cd ~/virtualenv; python -m venv search-notebook)
   $ source ~/virtualenv/search-notebook/bin/activate
   ```

2. Download and install

   For users:

   ```
   $ pip -v install here-search-demo --extra-index-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi/simple
   ```

   For contributors/developers:   

   ```
   $ git clone ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git
   $ cd search-notebook
   $ pip install -e .
   ```

3. Jupyter config

   ```
   $ jupyter nbextension enable --py widgetsnbextension
   $ jupyter labextension install @jupyterlab/geojson-extension
   $ python -m ipykernel install --user --name search_demo --display-name "search demo"
   ```

## Reference

- [HERE Geocoding & Search](https://developer.here.com/documentation/geocoding-search-api/dev_guide/index.html)
- [here_map_widget](https://here-map-widget-for-jupyter.readthedocs.io/en/latest/index.html)
- [ipywidgets](https://ipywidgets.readthedocs.io/en/latest/index.html)
- [asyncio](https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-1)
- [Effective Python environment](https://realpython.com/effective-python-environment/)
- [Launch your OSS](https://opensource.guide/starting-a-project/#launching-your-own-open-source-project)
- [GeoJS terms of services](https://www.geojs.io/tos/)
- [Macos extended charset](https://www.barcodefaq.com/knowledge-base/mac-extended-ascii-character-chart/)