Kubernetes deployment
=========================================
Create Namespace
-----
```
kubectl create namespace ansibledb 
```

Deploy mongodb
--------
```
# Add repo
helm repo add bitnami https://charts.bitnami.com/bitnami
# refresh helm repo 
helm repo update
# Deploy mongodb from values
helm  upgrade --install mongodb bitnami/mongodb -f ./mongo_values.yml -n ansibledb
```

Deploy ansibledb
--------
```
# review the yaml ansibledb-deployment.yml with appropriate values
kubectl apply -f ansibledb-deployment.yml -n ansibledb
```

