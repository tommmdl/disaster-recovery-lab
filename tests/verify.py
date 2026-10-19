#!/usr/bin/env python3
"""Recover across real clusters while the source workloads and controller are down."""
import datetime,fcntl,hashlib,json,os,subprocess,time,urllib.request,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local';SOURCE=ROOT.parent/'backup-restore-lab';KIT=LOCAL/'recovery-kit';os.umask(0o077)
locks=[]
for path in [LOCAL/'verify.lock',SOURCE/'.local/verify.lock']:
 f=open(path,'w');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(f)
(LOCAL/'verification.json').unlink(missing_ok=True)
plan=json.loads((KIT/'plan.json').read_text());expected=json.loads((KIT/'expected-private.json').read_text());images=json.loads((ROOT/'config/images.json').read_text());checks=[];tag=uuid.uuid4().hex[:8];restore='cross-cluster-'+tag;start=time.time();processes=[];snapshot=None;fence=False

def run(a,data=None,check=True):
 p=subprocess.run(a,input=data,capture_output=True)
 if check and p.returncode:raise RuntimeError((p.stdout+p.stderr).decode()[-4500:])
 return p

def k(side,ns,*a,data=None,check=True):
 script=(ROOT if side=='target' else SOURCE)/'scripts/k.sh'
 return run(['bash',str(script),'-n',ns,*a],data,check)
def obj(side,ns,kind,name):return json.loads(k(side,ns,'get',kind,name,'-o','json').stdout)
def v(*a):return run(['bash',str(ROOT/'scripts/v.sh'),*a])
def write(name,data):(LOCAL/name).write_text(json.dumps(data,indent=2)+'\n')
def wait(fn,timeout=600):
 end=time.monotonic()+timeout;last=None
 while time.monotonic()<end:
  try:
   result=fn()
   if result:return result
  except (OSError,ValueError,RuntimeError) as e:last=str(e)
  time.sleep(2)
 raise AssertionError('Timed out: '+str(last or fn))
def check(name,ok):
 assert ok,name
 checks.append(name);print('PASS:',name,flush=True)
def sql(side,ns,query):return k(side,ns,'exec','postgres-alpine-0','--','psql','-U','notes_admin','-d','notes','-Atc',query).stdout.decode().strip()
ROWS="SELECT coalesce(json_agg(n ORDER BY id),'[]'::json) FROM (SELECT id,title,created_at FROM notes) n"
SCHEMA="SELECT column_name,data_type,is_nullable,is_identity FROM information_schema.columns WHERE table_schema='public' AND table_name='notes' ORDER BY ordinal_position"
INDEXES="SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename='notes' ORDER BY indexname"
def api(path='/notes',body=None,method=None):
 req=urllib.request.Request('http://127.0.0.1:8022'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=8) as r:
  raw=r.read();return json.loads(raw) if raw else None

def probe_reachable():
 code='import socket; s=socket.create_connection(("'+source_ip+'",6443),timeout=3);s.close();print("connected")'
 return k('target','dr-probes','exec','api-probe','--','python','-c',code,check=False).returncode==0

def scale_source(ns,kind,name,count):return k('source',ns,'scale',kind+'/'+name,'--replicas='+str(count))
def restore_phase():
 r=obj('target','velero','restore',restore)
 return r if r.get('status',{}).get('phase') in ['Completed','PartiallyFailed','Failed','FailedValidation'] else None

try:
 source_system=obj('source','kube-system','namespace','kube-system');target_system=obj('target','kube-system','namespace','kube-system')
 check('Source and target are different Kubernetes clusters',source_system['metadata']['uid']!=target_system['metadata']['uid'])
 check('Target namespace does not exist before recovery',k('target','dr-notes','get','namespace','dr-notes',check=False).returncode!=0)
 check('Recovery kit has credentials and key without copied dump files',all((KIT/name).exists() for name in ['credentials','repository-password','plan.json']) and not any(KIT.glob('*.dump')))
 check('Target node has no source staging directory',run(['docker','exec','devops-recovery-control-plane','test','-e','/var/local/backup-restore-lab/backup-demo'],check=False).returncode!=0)
 check('Source sample and Velero belong to the backup lab',all(obj('source',ns,'namespace',ns)['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')=='backup-restore-lab' for ns in ['backup-demo','velero']))
 active=json.loads(k('source','velero','get','backups,restores','-o','json').stdout)['items']
 check('No source backup or restore is in progress',all(r.get('status',{}).get('phase') in ['Completed','PartiallyFailed','Failed','FailedValidation'] for r in active))
 source_ip=json.loads(run(['docker','inspect','devops-notes-control-plane']).stdout)[0]['NetworkSettings']['Networks']['kind']['IPAddress'];assert source_ip
 write('network.json',{'source_api_ip':source_ip,'target_node':'devops-recovery-control-plane'})
 # Only our target node is changed; never modify networking on the source cluster.
 run(['python3',str(ROOT/'scripts/network.py'),'clear'])
 probe_namespace={'apiVersion':'v1','kind':'Namespace','metadata':{'name':'dr-probes','labels':{'app.kubernetes.io/part-of':'disaster-recovery-lab'}}}
 k('target','dr-probes','apply','-f','-',data=json.dumps(probe_namespace).encode())
 probe={'apiVersion':'v1','kind':'Pod','metadata':{'name':'api-probe','namespace':'dr-probes'},'spec':{'automountServiceAccountToken':False,'securityContext':{'runAsNonRoot':True,'runAsUser':10001,'runAsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}},'containers':[{'name':'probe','image':images['api']['image'],'command':['python','-c','import time;time.sleep(7200)'],'resources':{'requests':{'cpu':'10m','memory':'32Mi'},'limits':{'cpu':'100m','memory':'96Mi'}},'securityContext':{'readOnlyRootFilesystem':True,'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}}}]}}
 k('target','dr-probes','apply','-f','-',data=json.dumps(probe).encode());k('target','dr-probes','wait','--for=condition=Ready','pod/api-probe','--timeout=180s');check('Target can reach the real source API before the fence',probe_reachable())
 source_api=obj('source','backup-demo','deployment','notes-api');source_db=obj('source','backup-demo','statefulset','postgres-alpine');source_velero=obj('source','velero','deployment','velero')
 snapshot={'api_replicas':source_api['spec']['replicas'],'db_replicas':source_db['spec']['replicas'],'velero_replicas':source_velero['spec']['replicas'],'rows':json.loads(sql('source','backup-demo',ROWS)),'schema':sql('source','backup-demo',SCHEMA),'indexes':sql('source','backup-demo',INDEXES),'sequence':sql('source','backup-demo','SELECT last_value,is_called FROM notes_id_seq'),'data_pvc_uid':obj('source','backup-demo','pvc','data-postgres-alpine-0')['metadata']['uid'],'dump_pvc_uid':obj('source','backup-demo','pvc','logical-backup')['metadata']['uid'],'main_image':obj('source','notes-lab','deployment','notes-api')['spec']['template']['spec']['containers'][0]['image'],'main_pvc_uid':obj('source','notes-lab','pvc','data-postgres-alpine-0')['metadata']['uid'],'source_ca':obj('source','backup-demo','configmap','kube-root-ca.crt')['data']['ca.crt']}
 write('source-recovery-private.json',snapshot);write('last-run.json',{'restore_name':restore,'backup_name':plan['backup_name'],'source_context':'kind-devops-notes','target_context':'kind-devops-recovery','target_namespace':'dr-notes','completed':False})
 scale_source('backup-demo','deployment','notes-api',0);k('source','backup-demo','wait','--for=delete','pod','-l','app=notes-api','--timeout=120s')
 scale_source('backup-demo','statefulset','postgres-alpine',0);k('source','backup-demo','wait','--for=delete','pod/postgres-alpine-0','--timeout=120s')
 scale_source('velero','deployment','velero',0);k('source','velero','wait','--for=delete','pod','-l','deploy=velero','--timeout=120s')
 fence=True;run(['python3',str(ROOT/'scripts/network.py'),'block'])
 check('Target workload cannot connect to the source control plane',not probe_reachable())
 check('Source API, PostgreSQL and Velero are scaled to zero',obj('source','backup-demo','deployment','notes-api')['spec']['replicas']==0 and obj('source','backup-demo','statefulset','postgres-alpine')['spec']['replicas']==0 and obj('source','velero','deployment','velero')['spec']['replicas']==0)
 # From this point installation and data recovery use only target API, saved credentials and S3.
 recovery_start=time.time();run(['python3',str(ROOT/'scripts/target.py')])
 wait(lambda:obj('target','velero','backupstoragelocation','default').get('status',{}).get('phase')=='Available')
 store=obj('target','velero','backupstoragelocation','default');check('Target uses a validated ReadOnly backup storage location',store['spec']['accessMode']=='ReadOnly')
 imported=wait(lambda:obj('target','velero','backup',plan['backup_name']) if obj('target','velero','backup',plan['backup_name']).get('status',{}).get('phase')=='Completed' else None)
 check('Target discovers completed backup metadata from S3 after source shutdown',imported['metadata']['uid']!=plan['backup_uid_at_source'] and imported['status'].get('errors',0)==0);write('imported-backup.json',imported)
 namespace={'apiVersion':'v1','kind':'Namespace','metadata':{'name':'dr-notes','labels':{'app.kubernetes.io/part-of':'disaster-recovery-lab'}}};k('target','dr-notes','create','-f','-',data=json.dumps(namespace).encode())
 target_ca=wait(lambda:obj('target','dr-notes','configmap','kube-root-ca.crt')['data']['ca.crt'])
 check('Target has a different, newly issued Kubernetes CA',target_ca!=snapshot['source_ca'])
 run(['python3',str(ROOT/'scripts/storage.py')])
 v('restore','create',restore,'--from-backup',plan['backup_name'],'--namespace-mappings','backup-demo:dr-notes','--resource-modifier-configmap','dr-restore-modifiers','--include-cluster-resources=false','--item-operation-timeout','5m')
 result=wait(restore_phase);write('restore.json',result)
 check('Cross-cluster Velero restore completes without errors',result['status']['phase']=='Completed' and result['status'].get('errors',0)==0)
 pvrs=json.loads(k('target','velero','get','podvolumerestores','-l','velero.io/restore-name='+restore,'-o','json').stdout)['items'];write('pod-volume-restores.json',pvrs)
 check('Kopia restores the dump volume on the new cluster',len(pvrs)==1 and pvrs[0]['status']['phase']=='Completed')
 k('target','dr-notes','wait','--for=condition=Ready','pod/backup-client','--timeout=180s');k('target','dr-notes','rollout','status','statefulset/postgres-alpine','--timeout=240s')
 check('Dump Pod runs on the target node rather than a source node',obj('target','dr-notes','pod','backup-client')['spec']['nodeName']=='devops-recovery-control-plane')
 pvc=obj('target','dr-notes','pvc','logical-backup');data_pvc=obj('target','dr-notes','pvc','data-postgres-alpine-0')
 check('Fresh dump and database PVCs do not reuse source identities',pvc['metadata']['uid']!=snapshot['dump_pvc_uid'] and data_pvc['metadata']['uid']!=snapshot['data_pvc_uid'])
 check('Dump storage class was mapped to the target local PV',pvc['spec']['storageClassName']=='dr-local-dump' and pvc['spec']['volumeName']=='dr-logical-dump')
 check('Source cluster CA did not overwrite the destination CA',obj('target','dr-notes','configmap','kube-root-ca.crt')['data']['ca.crt']==target_ca)
 check('Application Secret came back from the backup',hashlib.sha256(json.dumps(obj('target','dr-notes','secret','notes-db')['data'],sort_keys=True).encode()).hexdigest()==plan['source_secret_sha256'])
 check('Restored dump matches the pre-disaster SHA-256',k('target','dr-notes','exec','backup-client','--','sha256sum','/backup/notes.dump').stdout.decode().split()[0]==plan['dump_sha256'])
 check('Destination database is empty before logical restore',sql('target','dr-notes',"SELECT to_regclass('public.notes')")=='')
 k('target','dr-notes','exec','backup-client','--','sh','/scripts/restore.sh')
 check('Every backed-up row and field is restored in the second cluster',json.loads(sql('target','dr-notes',ROWS))==expected['rows'])
 check('Schema, indexes and identity sequence match the backup',sql('target','dr-notes',SCHEMA)==expected['schema'] and sql('target','dr-notes',INDEXES)==expected['indexes'] and sql('target','dr-notes','SELECT last_value,is_called FROM notes_id_seq')==expected['sequence'])
 k('target','dr-notes','scale','deployment/notes-api','--replicas='+str(snapshot['api_replicas']));k('target','dr-notes','rollout','status','deployment/notes-api','--timeout=180s')
 log=open(LOCAL/'access-test.log','w');p=subprocess.Popen(['bash',str(ROOT/'scripts/k.sh'),'port-forward','--address','127.0.0.1','service/notes-api','8022:80'],stdout=log,stderr=log);processes.append((p,log));wait(lambda:api('/readyz'),90);ready_seconds=round(time.time()-recovery_start)
 check('Recovered API serves all backed-up notes while the source is down',api()['notes']==expected['api_rows'])
 backup_ids={n['id'] for n in expected['rows']};later_ids={n['id'] for n in snapshot['rows']}-backup_ids
 check('Post-backup source writes are absent at the recovered point',bool(later_ids) and all(n['id'] not in later_ids for n in api()['notes']))
 new=api(body={'title':'Recovered in a second cluster — '+tag});check('Recovered database accepts a new identity-backed write',new['id']>max(backup_ids));api('/notes/'+str(new['id']),method='DELETE')
 old_pod=obj('target','dr-notes','pod','postgres-alpine-0')['metadata']['uid'];k('target','dr-notes','delete','pod','postgres-alpine-0','--wait=true');k('target','dr-notes','rollout','status','statefulset/postgres-alpine','--timeout=180s');wait(lambda:api('/readyz'),90)
 check('Recovered data survives replacement of the new database Pod',obj('target','dr-notes','pod','postgres-alpine-0')['metadata']['uid']!=old_pod and obj('target','dr-notes','pvc','data-postgres-alpine-0')['metadata']['uid']==data_pvc['metadata']['uid'] and api()['notes']==expected['api_rows'])
 check('Source API remains fenced until recovery verification ends',not probe_reachable() and obj('source','backup-demo','statefulset','postgres-alpine')['spec']['replicas']==0)
 write('restore-description.json',{'text':v('restore','describe',restore,'--details').stdout.decode()})
 pending_report={'executed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'backup_name':plan['backup_name'],'restore_name':restore,'source_cluster_uid':source_system['metadata']['uid'],'target_cluster_uid':target_system['metadata']['uid'],'source_context':'kind-devops-notes','target_context':'kind-devops-recovery','recovery_to_ready_seconds':ready_seconds,'backed_up_note_count':len(expected['rows']),'source_note_count_at_failure':len(snapshot['rows']),'restore_warnings':result['status'].get('warnings',0),'source_unavailable_during_recovery':True}
finally:
 # Recovery and rollback affect only resources captured in the owned backup namespace.
 errors=[]
 if fence:
  try:run(['python3',str(ROOT/'scripts/network.py'),'clear'])
  except Exception as e:errors.append(str(e))
 if snapshot:
  for ns,kind,name,count in [('backup-demo','statefulset','postgres-alpine',snapshot['db_replicas']),('backup-demo','deployment','notes-api',snapshot['api_replicas']),('velero','deployment','velero',snapshot['velero_replicas'])]:
   try:scale_source(ns,kind,name,count)
   except Exception as e:errors.append(str(e))
  for ns,kind,name in [('backup-demo','statefulset','postgres-alpine'),('backup-demo','deployment','notes-api'),('velero','deployment','velero')]:
   try:k('source',ns,'rollout','status',kind+'/'+name,'--timeout=240s')
   except Exception as e:errors.append(str(e))
 for process,log in processes:
  if process.poll() is None:process.terminate();process.wait(timeout=10)
  log.close()
 write('source-recovery-result.json',{'errors':errors,'source_replica_counts_restored':snapshot is not None and not errors,'target_source_api_fence_removed':not errors,'scope':'Restore the study source after the rehearsal, not a production traffic failback.'})
 if errors:raise RuntimeError('Source recovery needs attention: '+repr(errors))
# Final validations run after source rollback; no changes to its notes are made.
check('All current source rows and sequence survive the outage unchanged',json.loads(sql('source','backup-demo',ROWS))==snapshot['rows'] and sql('source','backup-demo','SELECT last_value,is_called FROM notes_id_seq')==snapshot['sequence'])
check('Original source database PVC is preserved',obj('source','backup-demo','pvc','data-postgres-alpine-0')['metadata']['uid']==snapshot['data_pvc_uid'])
check('Unrelated main lab image and PVC were untouched',obj('source','notes-lab','deployment','notes-api')['spec']['template']['spec']['containers'][0]['image']==snapshot['main_image'] and obj('source','notes-lab','pvc','data-postgres-alpine-0')['metadata']['uid']==snapshot['main_pvc_uid'])
check('Original source API connectivity returns after the rehearsal',probe_reachable())
k('target','dr-probes','delete','namespace','dr-probes','--wait=true','--timeout=90s')
result={**pending_report,'checks_passed':len(checks),'checks':checks,'duration_seconds':round(time.time()-start),'scope':'Real second kind cluster, distinct API server/CA/node/PVCs. Source sample API, PostgreSQL and Velero stopped; source API rejected from target node/pods during metadata sync, Kopia restore, SQL verification and CRUD. Main source cluster and its unrelated applications remain running. Same-host S3, no cloud/host-loss or production DNS failover claim.','final_state':'Source study replicas and target network rules restored; source notes unchanged; target recovered application retained.'};write('verification.json',result);write('last-run.json',{'restore_name':restore,'backup_name':plan['backup_name'],'source_context':'kind-devops-notes','target_context':'kind-devops-recovery','target_namespace':'dr-notes','completed':True});print(json.dumps(result,indent=2),flush=True)
