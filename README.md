[![Python package](https://github.com/heremaps/here-search-demo/actions/workflows/test.yml/badge.svg)](https://github.com/heremaps/here-search-demo/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/heremaps/here-search-demo/branch/main/graph/badge.svg?token=MVFCS4BUFN)](https://codecov.io/gh/heremaps/here-search-demo)

# HERE Search notebooks

A set of jupyter notebooks demonstrating the use of [HERE Geocoding & Search][4] endpoints `/autosuggest`,  `/discover`, `/browse`, and `/lookup`.

![searching for restaurants](docs/screenshot.png)

Requirements: a [HERE API key][1] and a Python environment.

The notebooks can be [used in your browser][3] without further installation.

## Installation

If you need to install the notebooks or the underlying library on your workstation, run preferably in a virtual environment:

   ```
   pip install here-search-demo
   ```

Link the virtual environment to a IPython kernel:

   ```
   python -m ipykernel install \
     --prefix $(python -c "import sys; print(sys.prefix)") \
     --name search_demo --display-name "search demo"
   ```


Use the `here-search-notebooks` script with your HERE API Key:

   ```
   API_KEY="your API key" here-search-notebooks
   ```
   
(More [details][2])

## License

Copyright (C) 2022-2023 HERE Europe B.V.

This project is licensed under the MIT license - see the [LICENSE](./LICENSE) file in the root of this project for license details.

[1]: https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start.html#get-an-api-key
[2]: docs/developers.md#setup-a-notebook-python-environment
[3]: https://heremaps.github.io/here-search-demo/lab/?path=demo.ipynb
[4]: https://developer.here.com/documentation/geocoding-search-api/dev_guide/index.html