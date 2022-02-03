# Search Notebook

A jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest` and `/discover`.

![searching for "statue of liberty"](screenshot.png)

    API_KEY="your api key" jupyter lab demo.py

## installation

1. Get A HERE [API key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key)
2. (Recommended) Create a virtual venv
3. Do
    ```
    pip install -r requirements.txt
    python -m ipykernel install --user --name demo_search --display-name "demo search"
    jupyter labextension develop --overwrite here_map_widget
    ```
   
<!-- To use jupyter notebook instead of jupyter lab
    jupyter nbextension enable --py widgetsnbextension
-->

## Reference

- [HERE Geocoding & Search](https://developer.here.com/documentation/geocoding-search-api/dev_guide/index.html)
- [here_map_widget](https://here-map-widget-for-jupyter.readthedocs.io/en/latest/index.html)
