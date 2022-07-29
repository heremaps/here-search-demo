# Search Notebook

A jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest`,  `/discover`, `/lookup`, `/revgeocode`,  and `/signals`.

![searching for restaurants](docs/screenshot.png)

To use it, you need a [HERE API key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key) and: 
- either a Python environment
- or a running Docker Desktop

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
   API_KEY="your API key" here-search-notebook
   ```
   
(More [details](docs/developers.md#setup-a-notebook-python-environment))

## Docker

Another way to run the notebook is to have it served by a Docker container.  
You can either start it manually or via the hosted docker-compose file.  
Therefor configure the **API_KEY** in the local **./docker-compose.yaml** file or in your bash as environment variable **API_KEY**.

---
### Docker-compose:

```
docker-compose up -d
```
---

### Manually:

1. Pull the latest image (optional)

   ```
   docker pull docker-local.artifactory.in.here.com/onesearch-demo:latest
   ```
2. Run a new container

   Use the Docker Desktop to run the image with the host port `8888` and the variable `API_KEY` set to your key. Or do:

   ```
   API_KEY=<YOUR_API_KEY> 
   docker run --name onesearch-demo -d -p 8888:8888 -e APY_KEY=$API_KEY docker-local.artifactory.in.here.com/onesearch-demo:latest
   ```

---

### Browse

Launch the notebook

Browse to http://127.0.0.1:8888/lab/tree/oneboxmap.ipynb?token=HERE
