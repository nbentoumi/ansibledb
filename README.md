AnsibleDB
=========================================
About
-----
AnsibleDB is Flask API Web server uses MongoDB as Database to store Ansible reports and ansible facts, this tool can be used to query hosts and facters managed Ansible as well search ansible logs.

Features
--------
* Store Ansible reports, users will be able to query Ansible logs and visualize tasks logs
* Ansible Reports will be available in Users Dashboard in stacked bar charts, bars charts are the stats of : Number of OK, Changed, Failures, Unreachable, Skipped, Rescued and Ignored for each Ansible run.
* Store Ansible facters, users will be able to build dynamic inventory for facters collected and custom facters as well.
* Users will be able to Query facters in the Web interface, command line using token or Swagger UI.
* Users can customize The inventory in settings, create personal token to query the API using curl commands or Swagger UI.

Architecture
--------
AnsibleDB is composed of 3 layers :
* playbook which gather facters and execute tasks, callback plugin send the facts and reports to the API server.
* AnsibleDB API which interacts with users, is a docker container.
* MongoDB which is the Database of the API server.

![image](https://github.com/nbentoumi/ansibledb/assets/6154423/0c6220b4-ec1b-420a-9617-6bd6ce6af6a1)



Getting started
---------------
* Install docker-compose
* copy docker-compose from the project https://github.com/nbentoumi/ansibledb/blob/main/ansibledb_server/docker-compose.yaml.
* Run: docker-compose up -d.
* Add the ansibledb callback plugin under callback_plugin, refrence : https://github.com/nbentoumi/ansibledb/tree/main/ansible_playbooks/callback_plugins.
* Enable callback plugin in ansible.cfg, refrence : https://github.com/nbentoumi/ansibledb/blob/main/ansible_playbooks/ansible.cfg.
* Run playbook, as an example https://github.com/nbentoumi/ansibledb/blob/main/ansible_playbooks/inventory.yml

in Docker-compose file, you can enable AD authentication by adding the variables below

      LDAP_SERVER: "ldaps://ldap_server:636", LDAP server
      LDAP_BASE_DN: "DC=company,DC=com", Base DN
      LDAP_FID_USERNAME: "CN=fid_ad_account,OU=Users,OU=OU Units,DC=company,DC=com", Active Directory account, will be used to map AD users. 
      LDAP_FID_PASSWORD: "password", password of Active Directory account.
      LDAP_REQUIRED_GROUP: "CN=AD_GROUP,OU=Groups,OU=OU Units,DC=company,DC=com", This variable is used to restrict access to AnsibleDB to only users member of AD group, this is optional, if not provided, all Authenticated users will be able to login to AnsibleDB.

AnsibleDB screenshots
---------------
* running playbook where we can see 3 changes and 3x8 OK tasks (3 hosts in inventory)
![image](https://github.com/nbentoumi/ansibledb/assets/6154423/e75e7c0c-beee-4d5a-bbf0-9ae494eaf1e8)


* Dashboard
in print screen below, we can see the hosts and ansible stats
![image](https://github.com/nbentoumi/ansibledb/assets/6154423/fc54a148-9e95-4888-90d0-c08950f258e2)


