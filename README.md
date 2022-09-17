# Search Widgets

A set of jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest`,  `/discover`, `/lookup`, `/revgeocode`,  and `/signals`.

![searching for restaurants](docs/screenshot.png)

Requirements: a [HERE API key][1] and a Python environment.

## Installation

   ```
   pip -v install here-search-widget --extra-index-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi/simple
   ```

   ```
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   python -m ipykernel install --user --name search_demo --display-name "search demo"
   ```

## Usage

   ```
   API_KEY="your API key" here-search-notebooks
   ```
   
(More [details][2])

[1]: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key
[2]: docs/developers.md#setup-a-notebook-python-environment