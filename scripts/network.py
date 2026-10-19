#!/usr/bin/env python3
"""Fence source API traffic only inside the dedicated target node."""
import ipaddress,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];mode=sys.argv[1];assert mode in ['block','clear']
state=json.loads((ROOT/'.local/network.json').read_text());ip=str(ipaddress.IPv4Address(state['source_api_ip']));node='devops-recovery-control-plane';assert state['target_node']==node
for chain in ['OUTPUT','FORWARD']:
 rule=['-d',ip,'-p','tcp','--dport','6443','-m','comment','--comment','disaster-recovery-lab','-j','REJECT']
 exists=subprocess.run(['docker','exec',node,'iptables','-C',chain,*rule],capture_output=True).returncode==0
 if mode=='block' and not exists:subprocess.run(['docker','exec',node,'iptables','-I',chain,'1',*rule],check=True)
 if mode=='clear' and exists:subprocess.run(['docker','exec',node,'iptables','-D',chain,*rule],check=True)
print('Scoped source API fence '+mode+' applied on '+node)
