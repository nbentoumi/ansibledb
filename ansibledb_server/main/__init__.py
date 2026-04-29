from flask import Flask, Blueprint, request, jsonify, send_from_directory, render_template, redirect, url_for, session, g
from flask_swagger_ui import get_swaggerui_blueprint
from flask_restx import Api, apidoc
from dotenv import load_dotenv
from pymongo import MongoClient
import logging
import os
import json
import ssl
import time


app = Flask(__name__)
app.secret_key = 'secret'

SUPPORTED_LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def normalize_log_level(log_level_name):
    if log_level_name is None:
        return 'INFO'

    normalized_level = str(log_level_name).upper()
    if normalized_level not in SUPPORTED_LOG_LEVELS:
        return 'INFO'

    return normalized_level


def apply_log_level(flask_app, log_level_name):
    normalized_level = normalize_log_level(log_level_name)
    log_level = getattr(logging, normalized_level, logging.INFO)

    flask_app.config['LOG_LEVEL'] = normalized_level
    flask_app.logger.setLevel(log_level)

    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.handlers = flask_app.logger.handlers
    werkzeug_logger.setLevel(log_level)

    logging.getLogger("gunicorn.error").setLevel(log_level)
    logging.getLogger("gunicorn.access").setLevel(log_level)

    return normalized_level


def configure_logging(flask_app):
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = '%(asctime)s %(levelname)s [%(name)s] %(message)s'
    gunicorn_logger = logging.getLogger("gunicorn.error")

    if gunicorn_logger.handlers:
        flask_app.logger.handlers = gunicorn_logger.handlers
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format))
        flask_app.logger.handlers = [handler]

    apply_log_level(flask_app, log_level_name)
    flask_app.logger.propagate = False


configure_logging(app)


@app.before_request
def log_request_start():
    g.request_started_at = time.time()


@app.after_request
def log_request(response):
    duration_ms = int((time.time() - getattr(g, 'request_started_at', time.time())) * 1000)
    username = session.get('user', 'anonymous')
    remote_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    app.logger.info(
        '%s %s %s %sms user=%s remote_addr=%s',
        request.method,
        request.path,
        response.status_code,
        duration_ms,
        username,
        remote_addr,
    )
    return response


@app.teardown_request
def log_request_exception(error):
    if error is not None:
        app.logger.exception('Unhandled exception during %s %s', request.method, request.path)

SWAGGER_URL = '/api/docs'  # URL for exposing Swagger UI (without trailing '/')
API_URL = "/static/swagger.json"  # Our API url (can of course be a local resource)
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    API_URL,
    config={
        'app_name': "AnsibleDB"
    },
)

api = Api(swaggerui_blueprint)
app.register_blueprint(swaggerui_blueprint)


load_dotenv()

MONGO_HOST = os.environ.get("MONGO_HOST")
MONGO_USER = os.environ.get("MONGO_USERNAME")
MONGO_PASS = os.environ.get("MONGO_PASSWORD")
MONGO_PORT = os.environ.get("MONGO_PORT")
MONGO_DB = os.environ.get("MONGO_DATABASE")

ANSIBLEDB_PORT = os.environ.get("ANSIBLEDB_PORT")


app.config['ADMIN_USERNAME'] = os.environ.get("ADMIN_USERNAME")
app.config['ADMIN_PASSWORD'] = os.environ.get("ADMIN_PASSWORD")
app.config['LDAP_FID_USERNAME'] = os.environ.get("LDAP_FID_USERNAME")
app.config['LDAP_FID_PASSWORD'] = os.environ.get("LDAP_FID_PASSWORD")
app.config['LDAP_SERVER'] = os.environ.get("LDAP_SERVER")
app.config['LDAP_BASE_DN'] = os.environ.get("LDAP_BASE_DN")
app.config['LDAP_REQUIRED_GROUP'] = os.environ.get("LDAP_REQUIRED_GROUP")
app.config['DEFAULT_INVENTORY_COLUMNS'] = ['hostname','default_ipv4','processor_vcpus','memtotal_mb','distribution','distribution_version','virtualization_type','virtualization_role']
app.config['REPORTS_KEEP_DAYS'] = 60
app.config['REPORTS_DISPLAY'] = 1
app.config['TOKEN_EXPIRE_DAYS'] = int(os.environ.get("TOKEN_EXPIRE_DAYS", 30))
app.config['LOG_LEVEL'] = normalize_log_level(os.environ.get("LOG_LEVEL", "INFO"))

uri = "mongodb://{}:{}@{}:{}/?authSource=admin".format(MONGO_USER, MONGO_PASS, MONGO_HOST, MONGO_PORT)
try:
    client = MongoClient(uri,serverSelectionTimeoutMS=10, connectTimeoutMS=20000)
    db = client[MONGO_DB]
    servers = db.servers
    # create index
    servers.create_index("ansible_facts.hostname")
    servers.create_index("ansible_reports.hostname")
    servers.create_index("ansible_reports.id")
    servers.create_index("ansible_reports.report_time")
    servers.create_index("facters")
    servers.create_index("username")

    admin_settings = servers.find_one({"username": 'admin'}, {"_id": 0, "log_level": 1})
    if admin_settings is not None:
        apply_log_level(app, admin_settings.get('log_level', app.config['LOG_LEVEL']))

except:
    msg="Unable to connect to Database"
    


