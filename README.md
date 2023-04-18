[![Python package](https://github.com/heremaps/here-search-demo/actions/workflows/test.yml/badge.svg)](https://github.com/heremaps/here-search-demo/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/heremaps/here-search-demo/branch/main/graph/badge.svg?token=MVFCS4BUFN)](https://codecov.io/gh/heremaps/here-search-demo)

# HERE Search notebooks

A set of jupyter notebooks demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest`,  `/discover`, `/browse`, and `/lookup`.

![searching for restaurants](docs/screenshot.png)

Requirements: a [HERE API key][1] and a Python environment.

## Installation

This package is soon to be found in pypi.

<!--
Run preferably in a virtual environment:

   ```
   pip -v install here-search-demo
   ```

Link the virtual environment to a IPython kernel:

   ```
   python -m ipykernel install \
     --prefix $(python -c "import sys; print(sys.prefix)") \
     --name search_demo --display-name "search demo"
   ```
-->

Currently, you need to `pip install` the git repository to get it running on you workstation. Refer to the 
[`developer notes`](https://github.com/heremaps/here-search-demo/blob/main/docs/developers.md) for details.


## Usage

   ```
   API_KEY="your API key" here-search-notebooks
   ```
   
(More [details][2])

[1]: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key
[2]: docs/developers.md#setup-a-notebook-python-environment

## License

Copyright (C) 2022-2023 HERE Europe B.V.

This project is licensed under the MIT license - see the [LICENSE](./LICENSE) file in the root of this project for license details.