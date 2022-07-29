## Developer notes

### Setup a Notebook Python environment

It is recommended to use a Python virtual environment. The below recipe uses the python batteries `venv` module.
It has only been tested on a Macos Monterey machine, but it should not be too difficult to use it on another Unix-like workstation.

1. Virtual environment

   ```
   mkdir -p ~/virtualenv; (cd ~/virtualenv; python -m venv search-notebook)
   source ~/virtualenv/search-notebook/bin/activate
   ```

2. Download and install

   For users:

   ```
   pip -v install here-search-demo --extra-index-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi/simple
   ```

   For contributors/developers:

   ```
   git clone ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git
   cd search-notebook
   pip install -e .
   ```

3. Jupyter config

   ```
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   python -m ipykernel install --user --name search_demo --display-name "search demo"
   ```


### Upload a new package to artifactory

    pip install twine wheel
    python setup.py sdist bdist_wheel
    twine upload --skip-existing --repository-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi dist/*

### Generate a Notebook Docker image

This recipe uses Jupyter Hub [`repo2docker`](https://repo2docker.readthedocs.io/en/latest/). 
It is used in the project `gitlab-ci.yml`. You need to have Docker Desktop installed and running.

In a virtual environment do:

   ```
   pip install jupyter-repo2docker
   jupyter-repo2docker \
     --no-run --image-name search-demo-repo2docker --user-name default \
     ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git
   ```

Optionally:

   ```
   docker save search-demo-repo2docker:latest | gzip > search-demo-repo2docker.tgz
   ```

### Alternate to run the Docker container

1. Pull the latest image

   ```
   docker pull docker-local.artifactory.in.here.com/onesearch-demo:latest
   ```
2. Run a new container

   Use the Docker Desktop to run the image with the variable `API_KEY` set to your key. Or do:

   ```
   docker run --name onesearch-demo -d -p 8888:8888 \
     -e APY_KEY=<YOUR_API_KEY> -e JUPYTER_TOKEN=HERE \
     docker-local.artifactory.in.here.com/onesearch-demo:latest
   ```



## External pointers

- [HERE Geocoding & Search](https://developer.here.com/documentation/geocoding-search-api/dev_guide/index.html)
- [here_map_widget](https://here-map-widget-for-jupyter.readthedocs.io/en/latest/index.html)
- [ipywidgets](https://ipywidgets.readthedocs.io/en/latest/index.html)
- [asyncio](https://bbc.github.io/cloudfit-public-docs/asyncio/asyncio-part-1)
- [Effective Python environment](https://realpython.com/effective-python-environment/)
- [Launch your OSS](https://opensource.guide/starting-a-project/#launching-your-own-open-source-project)
- [GeoJS terms of services](https://www.geojs.io/tos/)
- [Macos extended charset](https://www.barcodefaq.com/knowledge-base/mac-extended-ascii-character-chart/)