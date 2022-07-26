## Host the notebook in a Docker image

This recipe uses Jupyter Hub [`repo2docker`](https://repo2docker.readthedocs.io/en/latest/).  You need to have Docker Desktop installed and running. 

In a virtual environment do:

   ```
   $ pip install jupyter-repo2docker
   $ jupyter-repo2docker \
     --no-run --image-name search-demo-repo2docker --user-name default \
     ssh://git@main.gitlab.in.here.com:3389/olp/onesearch/playground/decitre/search-notebook.git
   $ docker save search-demo-repo2docker:latest | gzip > search-demo-repo2docker.tgz
   ```
