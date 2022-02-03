# Search Notebook

A jupyter notebook demonstrating the use of HERE Geocoding & Search endpoints `/autosuggest` and `/discover`.

![searching for "statue of liberty"](screenshot.png)

    API_KEY="your api key" jupyter lab demo.py


## Detailed installation guideline

This simplified method does not use pyenv or conda, but the python3 integrated `venv` module.
The recipe below runs on a macos Monterey machine.

1. Get A HERE [API key](https://developer.here.com/documentation/geocoding-search-api/dev_guide/topics/quick-start-dhc.html#get-an-api-key)

2. Clone the repo

   ```
   git clone ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git
   cd search-notebook
   ```
3. Run `install.sh`

   ```
   source install.sh
   ```

4. Run the demo in your virtualenv

   ```
   cd search-notebook
   source run.sh <your api key>
   ```

   You can jump to this step each time you need to start the demo.


## Reference

- [HERE Geocoding & Search](https://developer.here.com/documentation/geocoding-search-api/dev_guide/index.html)
- [here_map_widget](https://here-map-widget-for-jupyter.readthedocs.io/en/latest/index.html)
- [Effective Python environment](https://realpython.com/effective-python-environment/)