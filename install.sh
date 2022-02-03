mkdir virtualenv &&\
python3 -m venv virtualenv &&\
source virtualenv/bin/activate &&\
pip3 install -r requirements.txt &&\
python3 -m ipykernel install --user --name search_notebook --display-name "demo search"