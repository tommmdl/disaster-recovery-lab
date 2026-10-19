#!/usr/bin/env python3
"""Install the recovery controller using only the retained kit and target API."""
import json,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local';KIT=LOCAL/'recovery-kit';os.umask(0o077)
plan=json.loads((KIT/'plan.json').read_text());images=json.loads((ROOT/'config/images.json').read_text())
def run(a,data=None):return subprocess.check_output(a,input=data)
def k(*a,data=None):return run(['bash',str(ROOT/'scripts/k.sh'),*a],data)
existing=subprocess.run(['bash',str(ROOT/'scripts/k.sh'),'-n','velero','get','namespace','velero','-o','json'],capture_output=True)
if existing.returncode==0:assert json.loads(existing.stdout)['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')=='disaster-recovery-lab'
args=['bash',str(ROOT/'scripts/v.sh'),'install','--provider','aws','--plugins',images['aws_plugin']['image'],'--image',images['velero']['image'],'--bucket',plan['bucket'],'--secret-file',str(KIT/'credentials'),'--backup-location-config','region=us-east-1,s3ForcePathStyle=true,s3Url='+plan['s3_endpoint']+',checksumAlgorithm=','--restore-only','--use-volume-snapshots=false','--use-node-agent','--node-agent-pod-cpu-request=50m','--node-agent-pod-mem-request=128Mi','--node-agent-pod-mem-limit=768Mi','--velero-pod-cpu-request=100m','--dry-run','-o','json']
manifest=json.loads(run(args));items=manifest['items']
for item in items:
 if item['kind']=='Namespace':item['metadata'].setdefault('labels',{})['app.kubernetes.io/part-of']='disaster-recovery-lab'
 if item['kind']=='BackupStorageLocation':item['spec']['accessMode']='ReadOnly'
(LOCAL/'target-install-private.json').write_text(json.dumps(manifest))
pre=[i for i in items if i['kind'] in ['Namespace','CustomResourceDefinition']]
k('-n','velero','apply','-f','-',data=json.dumps({'apiVersion':'v1','kind':'List','items':pre}).encode());k('wait','--for=condition=Established',*[('crd/'+i['metadata']['name']) for i in pre if i['kind']=='CustomResourceDefinition'],'--timeout=120s')
remaining=[i for i in items if i['kind'] not in ['Namespace','CustomResourceDefinition']]
k('-n','velero','apply','-f','-',data=json.dumps({'apiVersion':'v1','kind':'List','items':remaining}).encode())
secret=k('-n','velero','create','secret','generic','velero-repo-credentials','--from-file=repository-password='+str(KIT/'repository-password'),'--dry-run=client','-o','json');k('-n','velero','apply','-f','-',data=secret)
modifier={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'dr-restore-modifiers','namespace':'velero'},'data':{'resource-modifiers.yaml':(ROOT/'config/restore-modifiers.yml').read_text()}};k('-n','velero','apply','-f','-',data=json.dumps(modifier).encode())
k('-n','velero','rollout','status','deployment/velero','--timeout=240s');k('-n','velero','rollout','status','daemonset/node-agent','--timeout=240s')
print('Recovery-only Velero installed on the target; backup metadata will sync from S3.')
