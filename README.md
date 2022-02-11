# Search Notebook

A jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest` and `/discover`.

![searching for "statue of liberty"](screenshot.png)

    
<code>API_KEY="[your api key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key)" here-search-notebook</code>

There is also a terminal version. An example with three terms buttons associated with the keys `[`, `]` and ``\``:

    >>> from search.terminal import OneBoxConsole
    >>> OneBoxConsole(latitude=40.71455, longitude=-74.00714, language="en", term_keys=b"[]\\").run()
    apiKey:
    -> sta
    | Statue | Starbucks | Station |
    Statue of Liberty-New York Access (Statue of Liberty)
    Starbucks
    NJ TRANSIT-Penn Station-New York
    Staten Island, NY, United States
    Stage Door Deli (Stage Door Pizza -Traditional NYC Style)


## Installation

    pip3 -v install git+ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git#egg=here-search-notebook

### step-by-step for non developers

This simplified method does not use pyenv or conda, but the python3 integrated `venv` module.
The recipe below runs on a macos Monterey machine.

1. Get A HERE [API key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key)

2. Do:

   ```
   mkdir virtualenv
   python3 -m venv virtualenv
   source virtualenv/bin/activate
   pip3 -v install git+ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git#egg=here-search-notebook
   jupyter nbextension enable --py widgetsnbextension
   jupyter labextension install @jupyterlab/geojson-extension
   python3 -m ipykernel install --user --name search_notebook --display-name "demo search"
   ```

3. Run the demo in your virtualenv

   ```
   cd search-notebook
   source virtualenv/bin/activate
   API_KEY="your api key" here-search-notebook
   ```


## Reference

- [HERE Geocoding & Search](https://developer.here.com/documentation/geocoding-search-api/dev_guide/index.html)
- [here_map_widget](https://here-map-widget-for-jupyter.readthedocs.io/en/latest/index.html)
- [ipywidgets](https://ipywidgets.readthedocs.io/en/latest/index.html)
- [Effective Python environment](https://realpython.com/effective-python-environment/)
- [Launch your OSS](https://opensource.guide/starting-a-project/#launching-your-own-open-source-project)
