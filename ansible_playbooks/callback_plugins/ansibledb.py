# Callback plugin  - send reports to ansibledb
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    name: ansibledb
    type: notification
    short_description: Sends events to AnsibleDB
    description:
      - This callback will report task events to AnsibleDB
    requirements:
      - whitelisting in configuration
      - requests (python library)
    options:
      url:
        description:
          - URL of the Ansibledb API.
        env:
          - name: ANSIBLEDB_URL
          - name: ANSIBLEDB_SERVER_URL
          - name: ANSIBLEDB_SERVER
        required: true
        ini:
          - section: callback_ansibledb
            key: url
      tz_utc:
        description:
          - Report time to utc otherwise runner time.
          - It can be set to 1.
        env:
          - name: ANSIBLEDB_TZ_UTC
        default: 1
        ini:
          - section: callback_ansibledb
            key: tz_utc
      enable_facts_caching:
        description:
          - Toggle to make the callback plugin cache facts to ansibledb. plugin will remove facts prefix 'ansible_' by default.
          - It can be set to 'false' to disable facts caching.
        env:
          - name: ANSIBLEDB_CACHE_FACTS
        default: 1
        ini:
          - section: callback_ansibledb
            key: enable_facts_caching
      ansible_facts_endpoint:
        description:
          - Endpoint of ansible_facts.
        env:
          - name: ANSIBLEDB_FACTS
        default: 'api/ansible_facts'
        ini:
          - section: callback_ansibledb
            key: ansible_facts_endpoint
      ansible_reports_endpoint:
        description:
          - Endpoint API of ansible reports.
        env:
          - name: ANSIBLEDB_REPORTS
        default: 'api/reports'
        ini:
          - section: callback_ansibledb
            key: ansible_reports_endpoint
      client_cert:
        description:
          - X509 certificate to authenticate to AnsibleDB if https is used
        env:
            - name: ANSIBLEDB_SSL_CERT
        default: /etc/ansibledb/client_cert.pem
        ini:
          - section: callback_ansibledb
            key: ssl_cert
          - section: callback_ansibledb
            key: client_cert
        aliases: [ ssl_cert ]
      client_key:
        description:
          - the corresponding private key
        env:
          - name: ANSIBLEDB_SSL_KEY
        default: /etc/ansibledb/client_key.pem
        ini:
          - section: callback_ansibledb
            key: ssl_key
          - section: callback_ansibledb
            key: client_key
        aliases: [ ssl_key ]
      verify_certs:
        description:
          - Toggle to decide whether to verify the AnsibleDB certificate.
          - It can be set to '1' to verify SSL certificates using the installed CAs or to a path pointing to a CA bundle.
          - Set to '0' to disable certificate checking.
        env:
          - name: ANSIBLEDB_SSL_VERIFY
        default: 1
        ini:
          - section: callback_ansibledb
            key: verify_certs
      disable_callback:
        description:
          - Toggle to make the callback plugin disable itself even if it is loaded.
          - It can be set to '1' to prevent the plugin from being used even if it gets loaded.
        env:
          - name: ANSIBLEDB_CALLBACK_DISABLE
        default: 0
'''

import os
from datetime import datetime
from ansible.parsing.ajson import AnsibleJSONEncoder
from collections import defaultdict
import json
import time
import sys
import difflib
from ansible import constants as C
from ansible.utils.color import stringc
from ansible.module_utils.common._collections_compat import MutableMapping

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from ansible.module_utils._text import to_text
from ansible.module_utils.parsing.convert_bool import boolean as to_bool
from ansible.plugins.callback import CallbackBase

def ansibledb_log(list_logs):
    """
    Prepare report to be sent to AnsibleDB API.
    """
    for data in list_logs:
        
        result = data.pop('result')
        task = data.pop('task')
        # don't send facts with reports
        remove_ansible_facts = result.pop("ansible_facts", None)
        # don't send invocation with reports
        remove_invocation = result.pop("invocation", None)
        # don't send facters with reports
        remove_facters = result.pop("facters", None)
        result['failed'] = data.get('failed')
        result['module'] = task.get('action')
        # cleanup result to reduce data being sent to AnsibleDB
        result_filtered=[]
        if isinstance(result, dict) and 'results' in result.keys():
            for res in result['results']:
                if isinstance(res,dict) and (('changed' in res.keys() and res['changed'] == True) or ('failed' in res.keys() and res['failed'] == True)):
                    result_filtered.append(res)
        result['results'] = result_filtered

        if data.get('failed'):
            level = 'err'
        elif result.get('changed'):
            level = 'notice'
        else:
            level = 'info'

        yield {
            "log": {
                'tasks': {
                    'task': task.get('name'),
                },
                'messages': {
                    'message': json.dumps(result, sort_keys=True),
                },
                'level': level,
            }
        }


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'ansibledb'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.items = defaultdict(list)

    def set_options(self, task_keys=None, var_options=None, direct=None):

        super(CallbackModule, self).set_options(task_keys=task_keys, var_options=var_options, direct=direct)

        if self.get_option('disable_callback'):
            self.disable_plugin('Callback disabled by environment.')

        self.ansibledb_url = self.get_option('url')
        self.ansible_facts_endpoint = self.get_option('ansible_facts_endpoint')
        try:
            self.enable_facts_caching = to_bool(self.get_option('enable_facts_caching'))
        except TypeError:
            self.enable_facts_caching = False

        try:
            self.tz_utc = to_bool(self.get_option('tz_utc'))
        except TypeError:
            self.tz_utc = False
        self.ansible_reports_endpoint = self.get_option('ansible_reports_endpoint')
        ssl_cert = self.get_option('client_cert')
        ssl_key = self.get_option('client_key')



        if not HAS_REQUESTS:
            self.disable_plugin(u'The `requests` python module is not installed')

        self.session = requests.Session()
        if self.ansibledb_url.startswith('https://'):
            if not os.path.exists(ssl_cert) or not os.path.exists(ssl_key) :
                self.session.verify = False
                requests.packages.urllib3.disable_warnings()
                self._display.warning(u"ANSIBLEDB SSL FILES not Found, SSL verification of %s disabled" % self.ansibledb_url,)
            elif os.path.exists(ssl_cert) and os.path.exists(ssl_cert):
                self.session.cert = (ssl_cert, ssl_key)
                self.session.verify = self.ssl_verify(str(self.get_option('verify_certs')))

    def get_report_time(self):
        """
        Return the current timestamp as a string to be sent over the network.
        """

        if self.tz_utc:
            return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S+00:00")
        else:
            return datetime.today().strftime("%Y-%m-%d %H:%M:%S+00:00")

    def disable_plugin(self, msg):
        self.disabled = True
        if msg:
            self._display.warning(msg + u' Disabling the AnsibleDB callback plugin.')
        else:
            self._display.warning(u'Disabling the AnsibleDB callback plugin.')

    def ssl_verify(self, option):
        try:
            verify = to_bool(option)
        except TypeError:
            verify = option

        if verify is False:
            requests.packages.urllib3.disable_warnings()
            self._display.warning(
                u"SSL verification of %s disabled" % self.ansibledb_url,
            )

        return verify

    def send_data(self, data_type, host, data):

        if data_type == 'report':
            #url = self.ansible_reports_endpoint
            url = '{ansibledb_url}/{reports_endpoint}'.format(ansibledb_url=to_text(self.ansibledb_url),reports_endpoint=to_text(self.ansible_reports_endpoint))
        elif data_type == 'ansible_facts':
            #url = self.ansible_facts_endpoint
            url = '{ansibledb_url}/{ansible_facts_endpoint}'.format(ansibledb_url=to_text(self.ansibledb_url),ansible_facts_endpoint=to_text(self.ansible_facts_endpoint))

        try:
            response = self.session.post(url=url, json=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            self._display.warning(u'Sending data to AnsibleDB at {url} failed for {host}: {err}'.format(
                host=to_text(host), err=to_text(err), url=to_text(url)))


    def send_reports_ansibledb(self, stats,report_time):
        """
        Send reports to AnsibleDB to be parsed by its config report
        importer. The data is in a format that AnsibleDB can handle
        without writing another report importer.
        """
        summary = {}
        for host in stats.processed.keys():
            total = stats.summarize(host)
            report = {
                "ansible_reports": {
                    "hostname": host,
                    "report_time": report_time,
                    "status": {
                        "ok": total['ok'],
                        "failed": total['failures'],
                        "unreachable": total['unreachable'],
                        "changed": total['changed'],
                        "skipped": total['skipped'],
                        "rescued": total['rescued'],
                        "ignored": total['ignored'],
                    },
                    "logs": list(ansibledb_log(self.items[host])),
                    "check_mode": self.check_mode,
                }
            }
            if self.check_mode:
                report['config_report']['status']['pending'] = total['changed']
                report['config_report']['status']['applied'] = 0

            self.send_data('report', host, report)
            self.items[host] = []

    def remove_prefix(self,text, prefix):
        """
        Remove prefix from text.
        """
        if text.startswith(prefix):
            return text[len(prefix):]
        return text

    def merge_dicts(self,x,y):
        """
        Merge discts x and y
        """
        z = x.copy()
        z.update(y)
        return z
    
    def send_ansible_facts(self,stats,report_time):
        """
        Send facts to AnsibleDB.
        """
        for host in stats.processed.keys():
            facts = {"hostname":host,"timestamp":report_time}
            total = stats.summarize(host)
            unreachable = int(total['unreachable'])
            ansible_facts = {}
            for data in self.items[host]:
                if 'ansible_facts' in data['result'].keys():
                    old_fact = data['result']['ansible_facts']
                    new_fact = {}
                    for key in old_fact.keys():
                        if key.startswith('ansible_'):
                            new_key = self.remove_prefix(key, 'ansible_')
                            new_fact[new_key] = old_fact[key]
                        elif key !='facts':
                            new_fact[key] = old_fact[key]
                        
                    #facts ={**facts, **new_fact}
                    facts = self.merge_dicts(facts,new_fact)
            ansible_facts = {"ansible_facts": facts}
            
            #send facts only if host is reachable otherwise host facts will be overided !
            if unreachable == 0:
                self.send_data('ansible_facts', host, ansible_facts)



    def send_reports_summary(self, stats,report_time):
        hosts = sorted(stats.processed.keys())
        url = self.ansibledb_url
        summary = {}
        for h in hosts:
            s = stats.summarize(h)
            summary[h] = s
        
        report_summary = {
            "ansible_reports": {
                "reported_at": report_time,
                "summary":summary
            }
        }

        try:
            response = self.session.post(url=url, json=report_summary)
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            self._display.warning(u'Sending data to AnsibleDB at {url} failed: {err}'.format(
                err=to_text(err), url=to_text(self.ansibledb_url)))
        
        return summary

    def _get_diff(self, difflist):
        """
        Return diff in array, so AnsibleDB Web, can display diff changes.
        """

        if not isinstance(difflist, list):
            difflist = [difflist]
 
        ret = []
        for diff in difflist:
            if 'dst_binary' in diff:
                ret.append(u"diff skipped: destination file appears to be binary\n")
            if 'src_binary' in diff:
                ret.append(u"diff skipped: source file appears to be binary\n")
            if 'dst_larger' in diff:
                ret.append(u"diff skipped: destination file size is greater than %d\n" % diff['dst_larger'])
            if 'src_larger' in diff:
                ret.append(u"diff skipped: source file size is greater than %d\n" % diff['src_larger'])
            if 'before' in diff and 'after' in diff:
                # format complex structures into 'files'
                for x in ['before', 'after']:
                    if isinstance(diff[x], MutableMapping):
                        diff[x] = self._serialize_diff(diff[x])
                    elif diff[x] is None:
                        diff[x] = ''
                if 'before_header' in diff:
                    before_header = u"before: %s" % diff['before_header']
                else:
                    before_header = u'before'
                if 'after_header' in diff:
                    after_header = u"after: %s" % diff['after_header']
                else:
                    after_header = u'after'
                before_lines = diff['before'].splitlines(True)
                after_lines = diff['after'].splitlines(True)
                if before_lines and not before_lines[-1].endswith(u'\n'):
                    before_lines[-1] += u'\n\\ No newline at end of file\n'
                if after_lines and not after_lines[-1].endswith('\n'):
                    after_lines[-1] += u'\n\\ No newline at end of file\n'
                differ = difflib.unified_diff(before_lines,
                                              after_lines,
                                              fromfile=before_header,
                                              tofile=after_header,
                                              fromfiledate=u'',
                                              tofiledate=u'',
                                              n=C.DIFF_CONTEXT)
                difflines = list(differ)
                if len(difflines) >= 3 and sys.version_info[:2] == (2, 6):
                    # difflib in Python 2.6 adds trailing spaces after
                    # filenames in the -- before/++ after headers.
                    difflines[0] = difflines[0].replace(u' \n', u'\n')
                    difflines[1] = difflines[1].replace(u' \n', u'\n')
                    # it also treats empty files differently
                    difflines[2] = difflines[2].replace(u'-1,0', u'-0,0').replace(u'+1,0', u'+0,0')
                has_diff = False
                for line in difflines:
                    has_diff = True
                    ret.append(line)
                if has_diff:
                    ret.append('\n')
            if 'prepared' in diff:
                ret.append(diff['prepared'])
        return u''.join(ret)

    def v2_on_file_diff(self, result):
        if result._task.loop and 'results' in result._result:
            for res in result._result['results']:
                if 'diff' in res and res['diff'] and res.get('changed', False):
                    diff = self._get_diff(res['diff'])
                    if diff:
                        result._result['diff'] = diff 
                        #self._display.display(diff)

        elif 'diff' in result._result and result._result['diff'] and result._result.get('changed', False):
            diff = self._get_diff(result._result['diff'])
            if diff:
                result._result['diff'] = diff 

    def diff_cleanup(self, result):
        """
        diff cleanup, keep diff only if there is a change .
        """
        if 'diff' in result._result.keys():
            #print(result._result['diff'])
            if isinstance(result._result['diff'],dict) and 'changed' in result._result['diff'].keys():
                if result._result['diff']['changed'] != True:
                    remove_diff = result._result.pop("diff", None)
                    result._result['diff'] = {}
                    #print('remove diff, changed false')
                    #print(result._result['diff']['changed'])
            elif isinstance(result._result['diff'],dict) and 'changed' not in result._result['diff'].keys():
                remove_diff = result._result.pop("diff", None)
                result._result['diff'] = {}
            elif isinstance(result._result['diff'],list) and len(result._result['diff']) >=0:
                result._result['diff'] = []

    def status_cleanup(self, result):
        """
        status cleanup, keep status only if there is a change .
        """
        ret_status = []
        if 'status' in result._result and result._result['status'] and result._result.get('changed', True):
            if 'Before' in result._result['status'].keys():
                ret_status.append('-before: '+result._result['status']['Before'])
            if 'After' in result._result['status'].keys():
                ret_status.append('+after: '+result._result['status']['After'])
            if 'ExecStart' in result._result['status'].keys():
                ret_status.append('ExecStart: '+result._result['status']['ExecStart'])
            result._result['status'] = ret_status
        elif 'status' in result._result and result._result['status'] and result._result.get('changed', False):
            result._result['status'] = []
        elif 'status' in result._result and 'changed' not in result._result['status'].keys():
            result._result['status'] = []        

    def append_result(self, result, failed=False):
        """
        Append result of host .
        """
        result_info = result._result
        task_info = result._task.serialize()
        task_info['args'] = None
        value = {}
        value['result'] = result_info
        value['task'] = task_info
        value['failed'] = failed
        host = result._host.get_name()
        self.items[host].append(value)
        self.check_mode = result._task.check_mode
        # override diff and keep only diff in result._result['diff']
        self.v2_on_file_diff(result)
        # cleanup diff dict if no change on task
        self.diff_cleanup(result)
        # cleanup status dict if no change on task
        self.status_cleanup(result)

    # Ansible callback API
    def v2_runner_on_failed(self, result, ignore_errors=False):
        self.append_result(result, True)

    def v2_runner_on_unreachable(self, result):
        self.append_result(result, True)

    def v2_runner_on_async_ok(self, result):
        self.append_result(result)

    def v2_runner_on_async_failed(self, result):
        self.append_result(result, True)

    def v2_playbook_on_stats(self, stats):
        # timestamp that will be sent to ansibleDB with reports and ansible_facts
        report_time = self.get_report_time()
        if self.enable_facts_caching:
            # Send Ansible facts to AnsibleDB
            self.send_ansible_facts(stats,report_time)
        # Send Ansible report to AnsibleDB
        self.send_reports_ansibledb(stats,report_time)

    def v2_runner_on_ok(self, result):
        self.append_result(result)
