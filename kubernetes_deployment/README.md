Kubernetes deployment
=========================================
Create Namespace
-----
```
kubectl create namespace ansibledb 
```

deploy mongodb
--------
```
# Add repo
helm repo add bitnami https://charts.bitnami.com/bitnami
# refresh helm repo 
helm repo update
# Deploy mongodb from values
helm  upgrade --install mongodb bitnami/mongodb -f ./mongo_values.yml -n ansibledb
```

deploy ansibledb
--------
