#!/bin/sh
gunicorn ansibledb:app --config gunicorn_config.py
