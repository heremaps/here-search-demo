## Host a multi-user jupyter hub

This has been tested on an intranet Centos 7 server.

## Install here-search in virtualenv

    git clone https://main.gitlab.in.here.com/olp/onesearch/playground/decitre/search-notebook.git
    cd search-notebook
    pyenv install 3.9.7
    pyenv virtualenv 3.9.7 search-notebook
    pyenv local search-notebook
    pip install -r requirements.txt

## Install Jupyterhub

    pip instal jupyterhub
    pip install jupyterhub-idle-culler
    sudo yum install npm
    sudo npm install -g configurable-http-proxy

### Configuration


sudo iptables -I INPUT 1 -p tcp --dport 8082 -j ACCEPT

#### jupyterhub.service

    cat << eof > jupyterhub.service
    [Unit]
    Description=JupyterHub Service
    After=multi-user.target
    
    [Service]
    Environment=PATH=$(dirname $(pyenv which python)):/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
    ExecStart=$(pyenv which jupyterhub) --ip 0.0.0.0 --port 8889 --config=$(pwd)/jupyterhub_config.py
    Restart=on-failure
    StandardOutput=syslog
    StandardError=syslog
    SyslogIdentifier=jupyterhub
    
    [Install]
    WantedBy=multi-user.target
    eof

    sudo cp jupyterhub.service /etc/systemd/system
    sudo chmod 664 /etc/systemd/system/jupyterhub.service

#### jupyterhub_config.py


    jupyterhub --generate-config



    cat << eof >> jupyterhub_config.py
    import sys
    c.JupyterHub.services = [
        {
            'name':'cull-idle',
            'admin': True,
            'command': [sys.executable, '$(pyenv which cull_idle_servers.py)', '--timeout=10800']
    }
    ]
    eof

#### Start

        systemctl start jupyterhub.service

## Jupyterhub lite




Reference: https://tljh.jupyter.org/en/latest/install/custom-server.html
