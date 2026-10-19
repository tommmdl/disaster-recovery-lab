#!/usr/bin/env python3
"""Download the pinned Linux amd64 CLI after checking its recorded SHA-256."""
import hashlib,json,platform,tarfile,urllib.request,os
from pathlib import Path
os.umask(0o077)
r=Path(__file__).resolve().parents[1];local=r/'.local';(local/'bin').mkdir(parents=True,exist_ok=True)
assert platform.system()=='Linux' and platform.machine()=='x86_64','Use Linux amd64 or WSL'
c=json.loads((r/'config/tools.json').read_text())['velero'];archive=local/'velero.tar.gz'
if not archive.exists():archive.write_bytes(urllib.request.urlopen(c['url'],timeout=60).read())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==c['sha256'],'Velero archive checksum mismatch'
with tarfile.open(archive) as t:
 data=t.extractfile('velero-v'+c['version']+'-linux-amd64/velero').read();target=local/'bin/velero';target.write_bytes(data);target.chmod(0o755)
print('Velero CLI '+c['version']+' checksum verified')
