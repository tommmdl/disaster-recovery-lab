#!/usr/bin/env python3
"""Prepare a private recovery kit and a distinct, owned target cluster."""
import json,subprocess,hashlib,datetime,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local';KIT=LOCAL/'recovery-kit';SOURCE=ROOT.parent/'backup-restore-lab';KUBE=ROOT.parent/'kubernetes-lab';os.umask(0o077);KIT.mkdir(parents=True,exist_ok=True)
def run(a):return subprocess.check_output(a)
def source(*a):return run(['bash',str(SOURCE/'scripts/k.sh'),*a])
mode=sys.argv[1] if len(sys.argv)>1 else 'all'
assert mode in ['kit','cluster','all']
if mode in ['kit','all']:
 state=json.loads((SOURCE/'.local/last-run.json').read_text());assert state.get('completed'),'Complete the backup-restore-lab rehearsal first'
 report=json.loads((SOURCE/'.local/verification.json').read_text());assert report['backup_name']==state['successful_backup']
 backup=json.loads(source('-n','velero','get','backup',state['successful_backup'],'-o','json'));assert backup['status']['phase']=='Completed' and backup['status'].get('errors',0)==0
 assert datetime.datetime.fromisoformat(backup['status']['expiration'].replace('Z','+00:00'))>datetime.datetime.now(datetime.timezone.utc),'Backup expired'
 expected=json.loads((SOURCE/'.local/expected-private.json').read_text());assert len(expected['rows'])==report['backed_up_note_count']
 for filename in ['credentials','repository-password']:
  data=(SOURCE/'.local'/filename).read_bytes();target=KIT/filename
  if target.exists():assert target.read_bytes()==data,'Recovery kit changed; preserve the original credentials'
  target.write_bytes(data);target.chmod(0o600)
 (KIT/'expected-private.json').write_text(json.dumps(expected,indent=2)+'\n')
 store=json.loads(run(['docker','inspect','backup-restore-s3']))[0];assert store['State']['Running'];endpoint='http://'+store['NetworkSettings']['Networks']['kind']['IPAddress']+':8333'
 secret=json.loads(source('get','secret','notes-db','-o','json'))
 plan={'backup_name':state['successful_backup'],'failed_backup_name':state['failed_backup'],'backup_uid_at_source':backup['metadata']['uid'],'source_context':'kind-devops-notes','source_namespace':'backup-demo','target_context':'kind-devops-recovery','target_namespace':'dr-notes','s3_endpoint':endpoint,'bucket':'velero','dump_sha256':report['dump_sha256'],'source_secret_sha256':hashlib.sha256(json.dumps(secret['data'],sort_keys=True).encode()).hexdigest(),'backup_expiration':backup['status']['expiration'],'source_backup_phase':'Completed'}
 (KIT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
if mode=='kit':
 print('Private recovery kit captured; retain it separately from the source cluster.')
 raise SystemExit(0)
assert all((KIT/name).exists() for name in ['credentials','repository-password','plan.json','expected-private.json']),'Capture and retain the recovery kit before the incident'
run(['python3',str(ROOT/'scripts/prepare-tools.py')])
clusters=run([str(KUBE/'.local/bin/kind'),'get','clusters']).decode().splitlines()
if 'devops-recovery' in clusters:
 assert (LOCAL/'cluster-owned').exists() and (LOCAL/'cluster-owned').read_text().strip()=='devops-recovery','Target cluster is not owned by this checkout'
 run([str(KUBE/'.local/bin/kind'),'export','kubeconfig','--name','devops-recovery','--kubeconfig',str(LOCAL/'kubeconfig')])
else:
 run([str(KUBE/'.local/bin/kind'),'create','cluster','--name','devops-recovery','--image','kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5','--config',str(ROOT/'cluster/kind.yaml'),'--kubeconfig',str(LOCAL/'kubeconfig'),'--wait','5m'])
 (LOCAL/'cluster-owned').write_text('devops-recovery\n')
(LOCAL/'kubeconfig').chmod(0o600)
print('Private recovery kit and independent kind-devops-recovery cluster prepared.')
