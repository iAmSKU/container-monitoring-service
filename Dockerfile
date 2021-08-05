FROM python:3.8-slim

RUN mkdir -p /home/app/
COPY src/ /home/app

WORKDIR /home/app/

RUN pip install six docker \
    && rm -rf /root/.cache/pip

CMD [ "python3" ,"-u", "container-monitoring-service-using-docker.py" ]

