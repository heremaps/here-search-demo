#!/bin/bash

for lib in hyperkit minikube docker docker-compose; do
  brew ls --versions $lib || brew install $lib
done

ip=$(minikube ip)
if ! minikube ip > /dev/null; then
  minikube start
  grep $ip /etc/hosts || echo "$ip docker.local" | sudo tee -a /etc/hosts > /dev/null
fi

eval $(minikube docker-env)
docker pull docker-local.artifactory.in.here.com/onesearch-demo:latest
if ! docker ps -f name=onesearch-demo > /dev/null; then
  docker run --name onesearch-demo -d -p 8888:8888 -e APY_KEY=$1 -e JUPYTER_TOKEN=HERE docker-local.artifactory.in.here.com/onesearch-demo:latest
fi
docker ps -f name=onesearch-demo
echo "Browse http://$ip:8888/lab/tree/obm_1_base.ipynb?token=HERE"
