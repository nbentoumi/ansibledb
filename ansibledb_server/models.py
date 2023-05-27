from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session
import json
from main import app, servers
class AnsibleDB():

    @staticmethod   
    def get_keys(query_keys,servers):
        cursor_keys = []
        keys = []
        try:
            cursor_keys = servers.find_one(query_keys)
            keys = list(cursor_keys['ansible_facts'].keys())
        except:
            keys = []
        return cursor_keys,keys

    @staticmethod
    def get_dict_keys(facters_list,cursor_keys):
        keys =[]
        if len(facters_list)>0:
            for fact in facters_list:
                if isinstance(cursor_keys['ansible_facts'][fact],dict):
                    keys.append(fact)
        return keys

    @staticmethod
    def get_list(query_list,filter_list):
        try:
            cursor_list = servers.find_one(query_list,filter_list)
            cursor_list_result = list(cursor_list['facters'])
        except:
            cursor_list_result = []
        return cursor_list_result

    @staticmethod
    def get_facters(cursor,dict_keys,fact):
        result = []
        for i in cursor:
            try:
                result.append({'hostname':i['ansible_facts']['hostname'],'facter':i['ansible_facts'][fact],'timestamp':i['ansible_facts']['timestamp']})
            except KeyError:
                for k in dict_keys:
                    try:
                        if k == 'packages':
                            pkgs = []
                            try:
                                if len(i['ansible_facts']['packages'][fact])>0:
                                    for pk in i['ansible_facts']['packages'][fact]:
                                        pkg = None
                                        if 'name' in pk.keys(): pkg = pk['name'] 
                                        if 'version' in pk.keys(): pkg = f"{pkg}-{pk['version']}"
                                        if 'release' in pk.keys(): pkg = f"{pkg}-{pk['release']}"
                                        if 'arch' in pk.keys(): pkg = f"{pkg}.{pk['arch']}"
                                        if pkg is not None: pkgs.append(pkg)
                                if pkgs != [] :
                                    result.append({'hostname':i['ansible_facts']['hostname'],'facter':pkgs,'timestamp':i['ansible_facts']['timestamp']})
                            except:
                                pass
                        else:
                            try:
                                result.append({'hostname':i['ansible_facts']['hostname'],'facter':i['ansible_facts'][k][fact],'timestamp':i['ansible_facts']['timestamp']})
                            except:
                                pass
                    except KeyError:
                        pass
        return result

    @staticmethod    
    def get_filter(facters_list,cursor_keys):
        fields = {"_id":0}
        if len(facters_list)>0:
            for fact in facters_list:
                try:
                    if isinstance(cursor_keys['ansible_facts'][fact],dict):
                        for kdict in cursor_keys['ansible_facts'][fact].keys():
                            #k = 'ansible_facts.'+fact+'.'+kdict
                            k = 'ansible_facts.{}.{}'.format(fact,kdict)
                            fields[k]=1
                    else:
                        #k = 'ansible_facts.'+fact
                        k = 'ansible_facts.{}'.format(fact)
                        fields[k]=1
                except:
                    pass
    
        return fields

    @staticmethod 
    def get_tokens(query):
        result = []
        try:
            curs = servers.find(query)
            for i in curs:
                try:
                    result.append({'username':i['username'],'token':i['token']})
                except:
                    pass
        except:
            result = []
        return result

    @staticmethod 
    def query_cursor(query,fields):
        result = []
        try:
            cursor = servers.find( query, fields )
            result = list(cursor)
        except:
            result = []
        return result

    @staticmethod
    def query_inventory(username):
        inventory = []
        query_keys = { "ansible_facts.hostname": {"$regex": '^.*'}}
        cursor_keys,keys = __class__.get_keys(query_keys,servers)
        #query_saved_facters_settings = {"facters":{"$regex":'^.*'}}
        query_saved_facters_settings = {"username":username}
        facters_settings_project = {"_id": 0,"facters":1}
        facters_list = __class__.get_list(query_saved_facters_settings,facters_settings_project)

        fields = {"_id":0}
        if len(facters_list)>1:
            fields = __class__.get_filter(facters_list,cursor_keys)
        else:
            facters_list = []
            for k in app.config['DEFAULT_INVENTORY_COLUMNS']:
                if k in keys:
                    facters_list.append(k)

            fields = __class__.get_filter(facters_list,cursor_keys)

        # set hostname in the first columns
        if 'hostname' in facters_list:
            index_hostname = facters_list.index('hostname')
            facters_list[index_hostname] = facters_list[0]
            facters_list[0] = 'hostname'

        query_inventory= { "ansible_facts.hostname": {"$regex": '^.*'}}
        inventory = __class__.query_cursor(query_inventory,fields)
        return inventory,facters_list,fields
    
    @staticmethod
    def manage_inventory_columns(username):
        query_saved_facters_settings = {"username":username}
        facters_settings_project = {"_id": 0,"facters":1}
        try:
            facters_settings = servers.find_one(query_saved_facters_settings,facters_settings_project)
            len_fact = len(facters_settings)
            #if user doesn't have inventory columns set, use defaults
            if len(facters_settings['facters']) <= 1:
                facters_settings['facters'] = app.config['DEFAULT_INVENTORY_COLUMNS']
        except:
            facters_settings = {}
            facters_settings['facters']= app.config['DEFAULT_INVENTORY_COLUMNS']
            

        query_keys = { "ansible_facts.hostname": {"$regex": '^.*'}}
        try:
            cursor = servers.find_one(query_keys)
            cursor_keys = list(cursor['ansible_facts'].keys())
        except:
            cursor_keys = []
            
        keys = []
        for k in cursor_keys:
            if k == "default_ipv4":
                keys.append(k)
            if not isinstance(cursor['ansible_facts'][k],dict):
              keys.append(k)
        return keys,facters_settings
        
    @staticmethod
    def delete_host(host):
        try:
            servers.delete_one({ "ansible_facts.hostname": host })
            result = jsonify({"message":"ok"})
        except:
            result = jsonify({"message":"failed"})
        return result
    @staticmethod
    def auth_token():
        try:
            token = request.headers['token']
        except KeyError:
            token = None
        
        if token is not None:
            query_token = {"username": {"$regex": '^.*'},"token":token}
            try:
                curs_token = servers.find(query_token)
                if len(list(curs_token))!=0:
                    return True
                else:
                    return False
            except:
                return False
        else:
            return False
    @staticmethod
    def get_report_rotate():
        query_rotate = {"username": 'admin'}
        query_project = {"_id":0,"keep_reports":1}
        try:
            curs_admin = servers.find(query_rotate,query_project)
            res=list(curs_admin)
            if len(res)!=0:
                try:
                    return res[0]['keep_reports']
                except:
                    return app.config['REPORTS_KEEP_DAYS']
            else:
                servers.update_one({"username":'admin'}, {"$set": { "keep_reports" : app.config['REPORTS_KEEP_DAYS'] } }, True)
                return app.config['REPORTS_KEEP_DAYS']
        except:
            servers.update_one({"username":'admin'}, {"$set": { "keep_reports" : app.config['REPORTS_KEEP_DAYS'] } }, True)
            return app.config['REPORTS_KEEP_DAYS']
    @staticmethod
    def auth_ldap_get_user_dn(username):
        user_dn = ""
        try:
            ldap_server = app.config['LDAP_SERVER']
            base_dn = app.config['LDAP_BASE_DN']
            object_class = f'(&(objectclass=user)(sAMAccountName={username}))'
            fid_user = app.config['LDAP_FID_USERNAME']
            fid_pass = app.config['LDAP_FID_PASSWORD']
            server = Server(ldap_server, get_info=ALL)
            connection = Connection(server,user=fid_user,password=fid_pass)
            if connection.bind():
                connection.search(base_dn,object_class, attributes=['DistinguishedName'])
                try:
                    user_dn = str(connection.entries[0]['distinguishedName'])
                except:
                    user_dn = ""
        except:
            user_dn = ""

        return user_dn

    @staticmethod
    def auth_ldap(username,password):
        msg = ""
        ldap_server = app.config['LDAP_SERVER']
        required_group = app.config['LDAP_REQUIRED_GROUP']
        base_dn = app.config['LDAP_BASE_DN']
        object_class = f'(&(objectclass=user)(sAMAccountName={username}))'
        #user = f'cn={username},{root_dn}'
        user = __class__.auth_ldap_get_user_dn(username)
        if user == "":
            msg = "Incorrect username or password"
            return False,msg
        else:
            server = Server(ldap_server, get_info=ALL)
            connection = Connection(server,user=user,password=password)
            if connection.bind():
                if required_group is not None:
                    connection.search(base_dn,object_class, attributes=['memberOf'])
                    response = json.loads(connection.response_to_json())
                    if required_group in  response['entries'][0]['attributes']['memberOf']:
                        return True,msg
                    else:
                        msg = "missing AD group"
                        return False,msg
                else:
                    return True,msg
            else:
                msg="Incorrect username or password"
                return False,msg
    
    @staticmethod
    def auth_admin(username,password):
        if (username == app.config['ADMIN_USERNAME'] and password == app.config['ADMIN_PASSWORD']):
            return True
        else:
            return False
    @staticmethod
    def check_dict(key,result):
        exist = False
        try:
            for val in result:
                if key in val.keys():
                    exist = True
        except:
            exist = False

        return exist

    @staticmethod
    def get_facter_stats(result):
        statistique = []
        if result !=[]:
            for fact in result:
                i=0
                if not __class__.check_dict(fact['facter'],statistique):
                    for fact_temp in result:
                        if fact['facter'] == fact_temp['facter']:
                            i=i+1
                    try:
                       statistique.append({fact['facter']:i})
                    except:
                        pass
        return statistique

    @staticmethod
    def query_hostname(host):
        result = []
        query_host = { "ansible_facts.hostname": host }
        project_host = {"_id": 0}
        cursor = servers.find(query_host)
        result = list(cursor)
        #result = json.dumps(list_result,default=str)
        return result
    @staticmethod
    def delete_report(report_time):
        try:
            servers.delete_one({ "ansible_reports.report_time": report_time })
            result = jsonify({"message":"ok"})
        except:
            result = jsonify({"message":"failed"})
        return result
    @staticmethod
    def rotate_report(report_time):
        try:
            query = { "ansible_reports.report_time": {"$lt": report_time}}
            servers.delete_many(query)
            result = jsonify({"message":"ok"})
        except:
            result = jsonify({"message":"failed"})
        return result

    @staticmethod 
    def get_dashboard_report_display_days(username):
        query_dashboard_display = {"username": username}
        project_dashboard_display = {"_id":0,"dashboard_reports_days":1}
        
        try:
            curs_dashboard_display = servers.find(query_dashboard_display,project_dashboard_display)
            res=list(curs_dashboard_display)
            if len(res)!=0:
                try:
                    return res[0]['dashboard_reports_days']
                except:
                    return app.config['REPORTS_DISPLAY']
            else:
                servers.update_one({"username":username}, {"$set": { "dashboard_reports_days" : app.config['REPORTS_DISPLAY'] } }, True)
                return app.config['REPORTS_DISPLAY']
        except:
            return app.config['REPORTS_DISPLAY']