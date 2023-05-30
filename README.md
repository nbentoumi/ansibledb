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



Getting started
---------------
