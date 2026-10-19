#!/usr/bin/env python3
"""Reserve a fresh dump PV on the new cluster's node; never bind a source PV."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(a,data=None):return subprocess.check_output(a,input=data)
def k(*a,data=None):return run(['bash',str(ROOT/'scripts/k.sh'),*a],data)
node='devops-recovery-control-plane';path='/var/local/disaster-recovery-lab/dr-notes';label={'app.kubernetes.io/part-of':'disaster-recovery-lab'}
run(['docker','exec',node,'mkdir','-p',path]);assert not run(['docker','exec',node,'ls','-A',path]).strip(),'Target dump directory already contains files; do not overwrite a recovery'
run(['docker','exec',node,'chown','70:70',path]);run(['docker','exec',node,'chmod','700',path])
resources=[{'apiVersion':'storage.k8s.io/v1','kind':'StorageClass','metadata':{'name':'dr-local-dump','labels':label},'provisioner':'kubernetes.io/no-provisioner','volumeBindingMode':'WaitForFirstConsumer'},{'apiVersion':'v1','kind':'PersistentVolume','metadata':{'name':'dr-logical-dump','labels':label},'spec':{'capacity':{'storage':'128Mi'},'accessModes':['ReadWriteOnce'],'persistentVolumeReclaimPolicy':'Retain','storageClassName':'dr-local-dump','local':{'path':path},'claimRef':{'namespace':'dr-notes','name':'logical-backup'},'nodeAffinity':{'required':{'nodeSelectorTerms':[{'matchExpressions':[{'key':'kubernetes.io/hostname','operator':'In','values':[node]}]}]}}}}]
for item in resources:k('apply','-f','-',data=json.dumps(item).encode())
print('Reserved target storage class and a fresh PV on '+node)
