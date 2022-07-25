## Host the notebook in a Docker image

This recipe uses Jupyter Hub [`repo2docker`](https://github.com/jupyterhub/repo2docker).

You need to have Docker Desktop installed and running. 

### Build the Docker image

In a virtual environment do:

   ```
   $ pip install jupyter-repo2docker
   $ jupyter-repo2docker ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git
   ```

After a while, you will get a URL to open in your browser: `http://127.0.0.1:<port>>/?token=<token>`

### Configure

In Jupyter lab started in the Docker image, open a terminal and do:

   ```
   $ conda update python
   $ pip install -e .
   $ jupyter nbextension enable --py widgetsnbextension
   $ jupyter labextension install @jupyterlab/geojson-extension
   ```

### Commit and save (Optional)

Identify the Docker container id, commit and save it:

   ```
   $ docker ps
   $ docker commit <container_id> search-demo-repo2docker
   $ docker save -o search-demo-repo2docker.tar search-demo-repo2docker
   $ gzip search-demo-repo2docker.tar
   ```

