# Recovery into a second cluster was verified

English · [Português](validation.md)

All **32 local checks passed**. The suite took 195 seconds; the recovered application became ready 124 seconds after target Velero installation began. That interval includes installation, metadata import, volume and SQL recovery, but not cluster creation or kit capture. It is not an SLO.

Clusters have distinct kube-system UIDs, CAs and nodes. The new node lacked the source staging directory. Backup storage validated as ReadOnly; Backup metadata was imported from S3 with a new UID after the source application and controller were stopped. The target probe could not connect to the source Kubernetes API.

Restore completed without errors and with two warnings. Kopia PodVolumeRestore completed on the new node. Both data and dump PVCs have different UIDs from source, and the dump storage class maps to dr-local-dump. The application Secret came from backup and the target CA was not overwritten.

All seven backed-up notes returned with every field, schema, index and identity sequence verified. The eighth, written later, remained only at source. The destination accepted a controlled write, which was deleted, and kept its data after replacing the PostgreSQL Pod. All occurred before clearing the fence and restarting source service.

Afterward, all eight source notes and its sequence exactly matched the pre-outage snapshot. Original replicas and connectivity returned without changing the main notes-lab application's image or PVC.

[Complete report](../evidence/verification.json) · [Imported backup](../evidence/imported-backup.json) · [Restore](../evidence/restore.json) · [Recovered volume](../evidence/pod-volume-restores.json) · [Source restoration](../evidence/source-recovery-result.json).

## Both warnings

The original local PV was not included among cluster resources. Looking it up in the backup archive raises a warning; the modifier removes its old reference and binds a separately reserved PV in the new cluster. UID, location, SHA-256, content and application reads verify recovery.

The other warning reports an existing kube-root-ca.crt that differs from backup. A different cluster has a different CA. The destination-generated object was retained, and that behavior was tested. Both warnings remain in the [description](../evidence/restore-description.txt) and status JSON.

## Limits and preparation

The source cluster was not destroyed. Only the backup study components were stopped, and its API was fenced inside the destination node. The main cluster remained operational; this does not claim whole-host loss or traffic failover testing. Shared S3 storage sits on the same computer.

Initial target creation failed because systemd could not create an inotify instance. We raised the runtime limit from 128 to 512 and repeated creation. The [adjustment record](../evidence/host-inotify.json) retains the reason and scope; existing labs were not restarted.
