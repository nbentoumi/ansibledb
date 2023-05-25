FROM python:3.8-alpine

WORKDIR /app

COPY requirements.txt requirements.txt
COPY ansibledb_server/ansibledb.py ansibledb.py
COPY ansibledb_server/models.py models.py
COPY docker/gunicorn_config.py gunicorn_config.py
COPY docker/entrypoint.sh entrypoint.sh
ADD ansibledb_server/main main

RUN pip3 install -r requirements.txt

ENTRYPOINT ["sh","entrypoint.sh"]
