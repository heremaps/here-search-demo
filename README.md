[![Python package](https://github.com/heremaps/here-search-demo/actions/workflows/test.yml/badge.svg)](https://github.com/heremaps/here-search-demo/actions/workflows/test.yml)
[![Codecov](https://codecov.io/gh/heremaps/here-search-demo/branch/master/graph/badge.svg)](https://codecov.io/gh/heremaps/here-search-demo)

# HERE Search notebooks


A set of jupyter notebooks demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest`,  `/discover`, `/browse`, and `/lookup`.

![searching for restaurants](docs/screenshot.png)

Requirements: a [HERE API key][1] and a Python environment.

## Installation

Run preferably in a virtual environment:

   ```
   pip install '.[lab]'
   ```

Link the virtual environment to a IPython kernel:

   ```
   python -m ipykernel install \
     --prefix $(python -c "import sys; print(sys.prefix)") \
     --name search_demo --display-name "search demo"
   ```

## Usage

   ```
   API_KEY="your API key" here-search-notebooks
   ```
   
(More [details][2])

[1]: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key
[2]: docs/developers.md#setup-a-notebook-python-environment
