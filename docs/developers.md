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
   pip -v install here-search-widget --extra-index-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi/simple
   ```

   For contributors/developers:

   ```
   git clone ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook-ext.git
   cd search-notebook
   pip install -e .
   ```

3. Jupyter config

   ```
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   python -m ipykernel install --user --name search_demo --display-name "search demo"
   ```

### Upload a new package to a pypa repository

   ```
   pip install twine build
   python -m build --wheel
   twine upload --skip-existing --repository-url https://artifactory.in.here.com/artifactory/api/pypi/onesearch-pypi dist/*
   ```

### Test on MacOS / python3.7

1. Build Python 3.7.9 for `pyenv`

   ```
   brew install zlib bzip2 openssl@1.1 readline xz
   CFLAGS="-I$(brew --prefix openssl)/include -I$(brew --prefix bzip2)/include -I$(brew --prefix readline)/include -I$(xcrun --show-sdk-path)/usr/include"
   LDFLAGS="-L$(brew --prefix openssl)/lib -L$(brew --prefix readline)/lib -L$(brew --prefix zlib)/lib -L$(brew --prefix bzip2)/lib"
   pyenv install 3.7.9
   ```

2. Create virtual environment

   ```
   pyenv virtualenv 3.7.9 venv3.7
   pyenv activate venv3.7
   pyenv local venv3.7 && python -V
   pip install -e .
   pip install -r requirements_dev.txt
   ```
