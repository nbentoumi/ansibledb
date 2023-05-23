from flask import Flask, Blueprint, request, jsonify, send_from_directory, render_template, redirect, url_for, session
from flask_swagger_ui import get_swaggerui_blueprint
from flask_restx import Api, apidoc
from dotenv import load_dotenv
from pymongo import MongoClient
import os
import json
import ssl


app = Flask(__name__)
app.secret_key = 'secret'

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

MONGO_HOST = os.environ.get("MONGOHOST")
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

except:
    msg="Unable to connect to Database"
    


