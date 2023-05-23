FROM python:3.8-alpine

WORKDIR /app

COPY requirements.txt requirements.txt
COPY ansibledb.py ansibledb.py
COPY models.py models.py
COPY gunicorn_config.py gunicorn_config.py
COPY entrypoint.sh entrypoint.sh
ADD main main

RUN pip3 install -r requirements.txt

ENTRYPOINT ["sh","entrypoint.sh"]
