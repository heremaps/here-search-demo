# Search Notebook

A jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest`,  `/discover`, `/lookup`, `/revgeocode`,  and `/signals`.

![searching for restaurants](docs/screenshot.png)

To use it, you need a [HERE API key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key) and: 
- either a Python environment
- or a running Docker Desktop

---

## Python

A typical way to run a Python notebook such as the `here-search-notebook`, is to use a local Python environment.

1. Install the Python package

   ```
   $ pip -v install here-search-demo --extra-index-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi/simple
   ```

2. Configure Jupyter

   ```
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   python -m ipykernel install --user --name search_demo --display-name "search demo"
   ```

3. Launch the notebook

   ```
   API_KEY="your API key" here-search-notebooks
   ```
   
(More [details](docs/developers.md#setup-a-notebook-python-environment))

---

## Docker

Another way to run the notebook is to have it served by a Docker container.

1. Docker compose
   Download  [`docker-compose.yaml`](https://main.gitlab.in.here.com/olp/onesearch/playground/decitre/search-notebook/-/raw/master/docker-compose.yaml?inline=false), 
set its variable `API_KEY` to your api key, and do:

   ```
   docker-compose up -d
   ```


3. Launch the base notebook

   Browse to http://127.0.0.1:8888/lab/tree/obm_1_base.ipynb?token=HERE

(Macos [recipe](docs/developers.md#docker-on-macos) without Docker Desktop)
