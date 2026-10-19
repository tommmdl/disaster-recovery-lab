# Recover before reopening writes

English · [Português](runbook.md)

Choose the recovery point and locate the bucket, S3 credentials and original Kopia password. A kit on the disk that was lost cannot support recovery. This portfolio's backup TTL is seven days; do not expect objects already removed by garbage collection.

## Before an incident

After backup-restore-lab completes, while the source is reachable:

```bash
bash scripts/lab.sh kit
```

Retain .local/recovery-kit/ privately. The plan records the exact backup name, dump hash and expiry. Expected test values are only a verification reference, not database restoration input. Never copy the folder into Git or public artifacts.

## With an unavailable source

Do not generate another kit by querying the lost source. Use retained inputs. Sibling kind/kubectl tools must be available or reinstalled; target creation does not use the source kubeconfig.

```bash
bash scripts/lab.sh create-target
bash scripts/lab.sh install-target
bash scripts/v.sh backup get
bash scripts/k.sh -n velero get backupstoragelocations
```

Wait for S3 synchronization. Select only a completed, error-free and unexpired backup. Target Velero should use ReadOnly storage. This does not replace S3 permissions or prevent every metadata, log or maintenance write.

Manual restoration requires a fresh destination: neither dr-notes nor its PV directory may contain an earlier recovery. Retain and investigate existing data instead of clearing a database just to make tests pass.

```bash
bash scripts/k.sh create namespace dr-notes
bash scripts/k.sh label namespace dr-notes app.kubernetes.io/part-of=disaster-recovery-lab
python3 scripts/storage.py
bash scripts/v.sh restore create manual-dr --from-backup BACKUP_NAME --namespace-mappings backup-demo:dr-notes --resource-modifier-configmap dr-restore-modifiers --include-cluster-resources=false --wait
bash scripts/v.sh restore describe manual-dr --details
bash scripts/k.sh -n velero get podvolumerestores
```

Check completed PodVolumeRestore, fresh PVCs, client placement on the new node and preservation of the destination certificate. Read restore warnings; zero errors alone do not verify data.

```bash
bash scripts/k.sh wait --for=condition=Ready pod/backup-client --timeout=180s
bash scripts/k.sh rollout status statefulset/postgres-alpine --timeout=240s
bash scripts/k.sh exec postgres-alpine-0 -- psql -U notes_admin -d notes -Atc "SELECT to_regclass('public.notes')"
```

The query must return empty and API replicas must remain zero. Only in that fresh destination:

```bash
bash scripts/k.sh exec backup-client -- sh /scripts/restore.sh
bash scripts/k.sh scale deployment/notes-api --replicas=2
bash scripts/k.sh rollout status deployment/notes-api --timeout=180s
bash scripts/access.sh
```

The restore script checks the checksum before applying SQL in one transaction. Compare API and database rows, schema, indexes and identity sequence. The automated test performs these checks and a controlled write before considering recovery complete.

## If the rehearsal stops halfway

Private .local/source-recovery-private.json records original replica counts and reference data. .local/network.json identifies the narrowly scoped API fence on the new node. .local/source-recovery-result.json records any automatic recovery errors.

```bash
python3 scripts/network.py clear
```

Only this lab's two rules for the recorded IP and port are removed; firewall tables are not flushed. If the study source remains stopped, restore backup-demo/notes-api, backup-demo/postgres-alpine and velero/velero replica counts from the snapshot. Local defaults were 2, 1 and 1; inspect the snapshot first.

Do not alter notes-lab or its Argo CD application to repair this exercise. Scripts use explicit contexts, but a manual command without kubeconfig can hit the wrong cluster. Keep using this project's wrappers and those from backup-restore-lab.

## Source return is not a database merge

The test deletes its controlled target write, removes the fence and reopens original replicas to keep study labs available. In production, choose an authoritative source before enabling writers and traffic. Post-backup writes in both databases may diverge; no replication or automatic reconciliation is implemented here. DNS and load-balancer traffic switching are not claimed.

## If another WSL node will not start

The observed error was Failed to create control group inotify object: Too many open files. kind documents shared inotify limits; this was neither disk exhaustion nor backup corruption. On this tested environment:

```bash
docker exec devops-notes-control-plane sysctl fs.inotify.max_user_instances
docker exec devops-notes-control-plane sysctl -w fs.inotify.max_user_instances=512
```

This setting is shared by the Docker/WSL kernel and changed only at runtime, from 128. No persistent configuration file changed. Inspect node startup logs before applying this diagnosis to another environment. [kind reference](https://kind.sigs.k8s.io/docs/user/known-issues/#pod-errors-due-to-too-many-open-files).
