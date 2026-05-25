FROM python:3.8-alpine

# Fix CVEs by updating all packages in a single layer
RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache \
        sqlite-dev \
        xz-libs \
        zlib-dev \
    && rm -rf /var/cache/apk/*
    
WORKDIR /app

COPY requirements.txt requirements.txt
COPY ansibledb.py ansibledb.py
COPY models.py models.py
COPY gunicorn_config.py gunicorn_config.py
COPY entrypoint.sh entrypoint.sh
ADD main main

RUN pip3 install -r requirements.txt

ENTRYPOINT ["sh","entrypoint.sh"]
