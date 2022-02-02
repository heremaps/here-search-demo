# AS/Search Notebook

    API_KEY="your api key" jupyter lab demo.py

## installation

    pip install -r requirements.txt
    python -m ipykernel install --user --name demo_search --display-name "demo search"
    jupyter nbextension enable --py widgetsnbextension
    jupyter labextension develop --overwrite here_map_widget
