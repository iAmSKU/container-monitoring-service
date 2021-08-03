#!/bin/bash

rm -rf *.tar

docker rmi -f container-monitoring-service:0.0.1

docker build --build-arg http_proxy=$http_proxy --build-arg https_proxy=$https_proxy -t container-monitoring-service:0.0.1 .

docker save -o container-monitoring-service.tar container-monitoring-service:0.0.1

chmod 755 container-monitoring-service.tar

