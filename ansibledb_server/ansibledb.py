"""
API Server for Ansible Reports and Facters, uses mongodb as Database.
2023 - Nasredine Bentoumi - nasredine.bentoumi@gmail.com
"""
from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError
from pymongo import MongoClient
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session
import os
import json
import ssl
import math
from datetime import datetime, timedelta 

from models import AnsibleDB
from main import app,servers,client

ansibledb = AnsibleDB()

@app.route('/inventory', methods = ['POST', 'GET'])
def index():
    """ Display servers inventory. """

    if('user' in session):
        username = session['user']
        host_delete = None
        if (request.method == 'POST'):
            host_delete = request.form.get('host_delete')
            if host_delete is not None:
                result = ansibledb.delete_host(host_delete)
        # Check DB connection, return to login if DB issue
        try:
            info = client.server_info()
        except:
            msg="Unable to connect to Database"
            return render_template("login.html",msg=msg)

        result,facters_list,fields = ansibledb.query_inventory(username)

        return render_template('servers.html', result=result,fields=fields,facters_list=facters_list)
    else:
        msg = 'Login with your AD account'
        return render_template("login.html",msg=msg)

@app.route('/server_facters', methods = ['POST', 'GET'])
def server_details():
    """ Display servers details. """

    if('user' in session):
        username = session['user']
        host_delete = None
        host_facters = None
        if (request.method == 'POST'):
            host_delete = request.form.get('host_delete')
            host_facters = request.form.get('host_facters')
            if host_delete is not None:
                result = ansibledb.delete_host(host_delete)
        try:
            info = client.server_info()
        except:
            msg="Unable to connect to Database"
            return render_template("login.html",msg=msg)

        result = ansibledb.query_hostname(host_facters)

        return render_template('hostname.html', username=username,host_facters=host_facters,result=result)
    else:
        msg = 'Login with your AD account'
        return render_template("login.html",msg=msg)

@app.route('/settings', methods = ['POST', 'GET'])
def settings():
    """ Manages user's settings: inventory columns, dashboard settings and tokens """

    if('user' in session):
        result = []
        rotate = None
        dashboard_reports = None
        username = session['user']
        if(request.method == 'POST'):
            save_facters_settings = request.form.get('save_facters_settings')
            token = request.form.get('token')
            rotate_reports = request.form.get('rotate_reports')
            dashboard_reports = request.form.get('dashboard_reports_days')
            user_token_to_delete = request.form.get('user_token_to_delete')
            token_to_delete = request.form.get('token_to_delete')
            # save inventory columns
            if save_facters_settings is not None:
                facters = save_facters_settings.split(",")
                servers.update_one({"username":username}, {"$set": { "facters" : facters } }, True)
            # dashboard default display days for user
            if dashboard_reports is not None:
                try:
                    servers.update_one({"username":username}, {"$set": { "dashboard_reports_days" : int(dashboard_reports) } }, True)
                except Exception as e:
                    return render_template("error.html", msg = str(e)) 
            # save rotate reports
            if rotate_reports is not None:
                try:
                    servers.update_one({"username":'admin'}, {"$set": { "keep_reports" : int(rotate_reports) } }, True)
                except Exception as e:
                    return render_template("error.html", msg = str(e)) 
            # save Token
            if token is not None:
                try:
                    servers.update_one({"username":username}, {"$set": { "token" : token } }, True)
                except Exception as e:
                    return render_template("error.html", msg = str(e)) 
            # delete token
            if user_token_to_delete is not None and token_to_delete is not None:
                try:
                    servers.delete_one({"username":user_token_to_delete,"token":token_to_delete})
                except Exception as e:
                    return render_template("error.html", msg = str(e))

        try:
            info = client.server_info()
        except:
            msg="Unable to connect to Database"
            return render_template("login.html",msg=msg)
        
        dashboard_reports = int(ansibledb.get_dashboard_report_display_days(username))
        if username == 'admin':
            query = {"username": {"$regex": '^.*'}}
            result = ansibledb.get_tokens(query)
            rotate = ansibledb.get_report_rotate()
        else:
            query = {"username": username}
            result = ansibledb.get_tokens(query)


        keys,facters_settings = ansibledb.manage_inventory_columns(username)
        return render_template('settings.html', keys=keys, facters_settings=facters_settings,result=result,username=username,rotate=rotate,dashboard_reports_days=dashboard_reports)
    else:
        msg = 'login with your AD account'
        return render_template("login.html",msg=msg)



@app.route('/token', methods = ['POST', 'GET'])
def token():
    """ Manage users token, handled in settings instead """

    if('user' in session):
        username = session['user']
        result = []
        if(request.method == 'POST'):
            result=[]
            token = request.form.get('token')
            user_token_to_delete = request.form.get('user_token_to_delete')
            token_to_delete = request.form.get('token_to_delete')
            if token is not None:
                try:
                    servers.update_one({"username":username}, {"$set": { "token" : token } }, True)
                except Exception as e:
                    return render_template("error.html", msg = str(e))
            if user_token_to_delete is not None and token_to_delete is not None:
                try:
                    servers.delete_one({"username":user_token_to_delete,"token":token_to_delete})
                except Exception as e:
                    return render_template("error.html", msg = str(e))
        if session['user'] == 'admin':
            query = {"username": {"$regex": '^.*'}}
            result = ansibledb.get_tokens(query)
        else:
            query = {"username": username}
            result = ansibledb.get_tokens(query)

        return render_template('token.html', username=username,result=result)
    else:
        msg = 'login with your AD account'
        return render_template("login.html",msg=msg)

@app.route('/facters', methods = ['POST', 'GET'])
def facters():
    """ query servers facters. """
    if(request.method == 'POST'):
        fact = request.form.get('facter')
    else:
        fact = None
    if('user' in session):
        try:
            info = client.server_info()
        except:
            msg="Unable to connect to Database"
            return render_template("login.html",msg=msg)

        if fact is None:
            result =[]
            statistique=[]
            project=""
            project_var = ""
            query = { "ansible_facts.hostname": {"$regex": '^.*'}}
            cur,keys = ansibledb.get_keys(query,servers)
            dict_keys = ansibledb.get_dict_keys(keys,cur)
        else:
            result = []
            project=""
            project_var = ""
            query = { "ansible_facts.hostname": {"$regex": '^.*'}}
            cur,keys = ansibledb.get_keys(query,servers)
            dict_keys = ansibledb.get_dict_keys(keys,cur)

            if fact in keys:
                project_var = "ansible_facts.{}".format(fact)
            else:
                for k in dict_keys:
                    if fact in cur['ansible_facts'][k].keys():
                        project_var = "ansible_facts.{}.{}".format(k,fact)
                        
            if project_var =="":
                project = {"_id":0}
            else:
                project = {"_id":0,'ansible_facts.hostname': 1, project_var: 1,'ansible_facts.timestamp': 1}
                    
            query = { "ansible_facts.hostname": {"$regex": '^.*'}}
            cursor = servers.find(query,project)
            result = ansibledb.get_facters(cursor,dict_keys,fact)
            statistique = ansibledb.get_facter_stats(result)

        return render_template('facters.html', keys=keys,dict_keys=dict_keys, fact=fact,result=result,statistique=statistique)
    else:
        msg = 'login with your AD account'
        return render_template("login.html",msg=msg)


@app.route('/login', methods = ['POST', 'GET'])
def login():
    """ authenticate users """

    if ('user' in session):
        session.pop('user')

    if(request.method == 'POST'):
        username = request.form.get('username')
        password = request.form.get('password')
        ldap_auth_status,msg = ansibledb.auth_ldap(username,password)
        if (ansibledb.auth_admin(username,password)) or (ldap_auth_status):
            session['user'] = username
            session['auth'] = True
            return redirect('/')

        return render_template("login.html",msg=msg)
    return render_template("login.html")

@app.route('/logout')
def logout():
    """ Logout users and clear session. """

    if ('user' in session):
        #remove the session from the browser
        session.pop('user')
    return redirect('/login')


@app.route('/api/ansible_facts', methods=['POST'])
def ansible_facts():

    result = jsonify({"message":"failed"})
    if request.method == 'POST':
        content = json.loads(request.data)
        if 'hostname' in content["ansible_facts"].keys():
            host =  content["ansible_facts"]["hostname"]
            try:
                servers.update_one({"ansible_facts.hostname":host}, {"$set": content }, True)
                result = jsonify({"message":"ok"})

            except:
                result = jsonify({"message":"failed"})
    return result

@app.route('/', methods = ['POST', 'GET'])
def dashboard():
    """ dashboard"""
    if('user' in session):
        username = session['user']
        report_delete = None
        report_search = ""
        dashboard_reports_days = int(ansibledb.get_dashboard_report_display_days(username))
        report_period_start = None
        report_period_end = None
        report_period_start = (datetime.now() - timedelta(days=dashboard_reports_days)).strftime("%Y-%m-%d %H:00:00+00:00")
        report_period_end = datetime.now().strftime("%Y-%m-%d %H:00:00+00:00")
        report_search = (datetime.now() - timedelta(days=dashboard_reports_days)).strftime("%Y-%m-%d %H:00:00+00:00")
        query = { "ansible_reports.report_time": {"$gte": report_search}}
        
        if (request.method == 'POST'):
            report_delete = request.form.get('report_delete')
            report_period_start = request.form.get('report_period_start')
            report_period_end = request.form.get('report_period_end')


            if report_delete is not None:
                result = ansibledb.delete_report(report_delete)
            
            if report_period_start is not None and report_period_end is not None:
                query = { "ansible_reports.report_time": {"$gte": report_period_start, "$lt": report_period_end}}
            elif report_period_start is None and report_period_end is None:
                report_period_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:00:00+00:00")
                report_period_end = datetime.now().strftime("%Y-%m-%d %H:00:00+00:00")
                report_search = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:00:00+00:00")
                query = { "ansible_reports.report_time": {"$gte": report_search}}
                

        # Check DB connection, return to login if DB issue
        try:
            info = client.server_info()
        except:
            msg="Unable to connect to Database"
            return render_template("login.html",msg=msg)

        project = {"_id":0}
        cursor = servers.find(query,project)
        result = list(cursor)
        summary=[]
        for res in result:
            report_time = res['ansible_reports']['report_time']
            sum = {}
            for key in res.keys():
                if key!='summary' and key!='ansible_reports':
                    stat = {key:{'status':res[key]['ansible_reports']['status']}}
                    sum = {**sum, **stat}
            summary.append({'report_time':report_time,'summary':sum})
            
    
        return render_template("dashboard.html",summary=summary,report_period_start=report_period_start,report_period_end=report_period_end,dashboard_reports_days=dashboard_reports_days,username=username)    
    else:
        msg = 'login with your AD account'
        return render_template("login.html",msg=msg)
    
@app.route('/api/reports', methods=['POST', 'GET'])
def ansible_reports():
    """ Add reports to AnsibleDB"""
    content = json.loads(request.data)
    
    if 'hostname' in content["ansible_reports"].keys():
        hostname =  content["ansible_reports"]["hostname"]
        report_time =  content["ansible_reports"]["report_time"]
        try:
            servers.update_one({"ansible_reports.report_time":report_time}, {"$set": {hostname:content} }, True)
            result = jsonify({"message":"ok"})
            # Rotate reports after each reports added 
            rotate =  int(ansibledb.get_report_rotate())
            report_search = (datetime.now() - timedelta(days=rotate)).strftime("%Y-%m-%d %H:00:00+00:00")
            result_rotate = ansibledb.rotate_report(report_search)
        except:
            result = jsonify({"message":"update failed"})
    elif 'summary' in content["ansible_reports"].keys():
        report_time =  content["ansible_reports"]["reported_at"]
        summary =  content["ansible_reports"]["summary"]
        try:
            servers.update_one({"ansible_reports.report_time":report_time}, {"$set": {"summary":summary }}, True)
            count_summary = count_summary + 1
            result = jsonify({"message":"ok"})
        except:
            result = jsonify({"message":"update failed"})
    
            
    return result
    
@app.route('/node_report', methods = ['POST', 'GET'])
def report_details():
    """ Display servers reports details. """

    if('user' in session):
        result = []
        username = session['user']
        report_time = None
        hostname = None
        if (request.method == 'POST'):
            report_time = request.form.get('host_report_time')
            hostname = request.form.get('hostname')

        try:
            info = client.server_info()
        except:
            msg="Unable to connect to Database"
            return render_template("login.html",msg=msg)

        query = { "ansible_reports.report_time": report_time}
        summary = 'summary.{}'.format(hostname)
        report = '{}.ansible_reports'.format(hostname)
        project = {"_id":0,summary:1,report:1}
        try:
            cursor = servers.find(query,project)
            list_result = list(cursor)
            result = list_result[0][hostname]['ansible_reports']['logs']
            status = list_result[0][hostname]['ansible_reports']['status']
        except Exception as e:
            return render_template("error.html", msg = str(e)) 

        res = []
        for lg in result:
            if isinstance(lg['log']['messages']['message'],str):
                task = json.loads(lg['log']['messages']['message'])
                res.append({'task':lg['log']['tasks']['task'],'message':task})
            

        
        return render_template('node_report.html', result=res,status=status,hostname=hostname,report_time=report_time)
    else:
        msg = 'Login with your AD account'
        return render_template("login.html",msg=msg)

@app.route('/api/reports_summary', methods=['POST', 'GET'])
def ansible_reports_summary():
    """ Update report summary - not used for now"""
    content = json.loads(request.data)
    report_time =  content["ansible_reports_summary"]["reported_at"]
    summary =  content["ansible_reports_summary"]["summary"]

    try:
        servers.update_one({"ansible_reports_summary.report_time":report_time}, {"$set": {"summary":summary }}, True)
    except:
        content = jsonify({"message":"update failed"})
    return '200'

@app.route('/api/servers', methods=['GET'])
def ansibleservers():
    """ Query facters and servers"""    
    if ansibledb.auth_token():
        hostname = request.args.get('host',None)
        facts = request.args.get('fact',None)
        query = { "ansible_facts.hostname": {"$regex": '^.*'}}
        cur,keys = ansibledb.get_keys(query,servers)
        dict_keys = ansibledb.get_dict_keys(keys,cur)
        if hostname is None and facts is None:
            query = { "ansible_facts.hostname": {"$regex": '^.*'}}
            cursor = servers.find(query)
            list_result = list(cursor)
            result = json.dumps(list_result,default=str)
        elif hostname is None and facts is not None:
            fact=facts
            query = { "ansible_facts.hostname": {"$regex": '^.*'}}
            cursor = servers.find({}, {'_id': False})
            list_result = ansibledb.get_facters(cursor,dict_keys,fact)
            result = json.dumps(list_result,default=str)
        elif  hostname is not None:
            myquery = { "ansible_facts.hostname": hostname }
            cursor = servers.find(myquery)
            if facts is None:
                list_result = list(cursor)
                result = json.dumps(list_result,default=str)
            else:
                fact=facts
                list_result = ansibledb.get_facters(cursor,dict_keys,fact)
                result = json.dumps(list_result,default=str)
    else:
        result = jsonify({"failed":"token required"})
    return result

@app.route('/api/facters/<string:name>', methods=['GET'])
def list_facters(name: str):
    """  Query Facters """
    if ansibledb.auth_token():
      fact=name
      query = { "ansible_facts.hostname": {"$regex": '^.*'}}
      cur,keys = ansibledb.get_keys(query,servers)
      dict_keys = ansibledb.get_dict_keys(keys,cur)
      cursor = servers.find({}, {'_id': False})
      list_result = ansibledb.get_facters(cursor,dict_keys,fact)
      result = json.dumps(list_result,default=str)
    else:
      result = jsonify({"failed":"token required"})
    return result

@app.route('/api/servers/<string:name>/delete', methods=['GET','POST','DELETE'])
def delete_server(name: str):
    """ Delete nodes from AnsibleDB API"""
    if ansibledb.auth_token() and request.method == 'DELETE':
        host=name
        result = ansibledb.delete_host(host)
    else:
      result = jsonify({"message":"failed"})
    return result

@app.route('/api/facters', methods=['GET'])
def get_all_facters():
    result= {}
    return result
    
@app.errorhandler(404)
def page_not_found(error):
    """ Handle 404 error"""
    return render_template("error.html",msg=404)

if __name__ == '__main__':
    app.run(debug=True)
