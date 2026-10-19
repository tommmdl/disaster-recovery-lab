# Recuperar antes de reabrir escritas

[English](runbook.en.md) · Português

Escolha o ponto de recuperação e confirme onde estão o bucket, as credenciais S3 e a senha original do Kopia. Um kit guardado no mesmo disco que foi perdido não resolve a recuperação. O TTL do backup deste portfólio é de sete dias; não espere encontrar objetos já removidos pelo garbage collector.

## Antes do incidente

Com o backup-restore-lab concluído e a origem acessível:

```bash
bash scripts/lab.sh kit
```

Guarde `.local/recovery-kit/` privadamente. O plano registra o nome exato do backup, o hash do dump e a validade. A referência dos valores esperados serve para testar o resultado, sem ser aplicada como dados. Não copie esta pasta para o Git nem para artefatos públicos.

## Com a origem indisponível

Não tente gerar outro kit consultando a origem perdida. Use o que já foi preservado. As ferramentas kind/kubectl do checkout irmão precisam estar disponíveis ou ser instaladas novamente; o comando de criação não usa o kubeconfig de origem.

```bash
bash scripts/lab.sh create-target
bash scripts/lab.sh install-target
bash scripts/v.sh backup get
bash scripts/k.sh -n velero get backupstoragelocations
```

Espere a importação pelo S3. Escolha somente o backup concluído, sem erros e dentro da validade. O destino deve usar ReadOnly no Velero. Isso não substitui permissões próprias do S3 nem impede todo tipo de escrita de logs ou manutenção.

Para repetir manualmente a parte de restauração, o destino precisa estar novo: `dr-notes` e o diretório do PV não podem conter uma recuperação anterior. Se já houver dados, preserve-os e investigue; não limpe um banco apenas para passar no teste.

```bash
bash scripts/k.sh create namespace dr-notes
bash scripts/k.sh label namespace dr-notes app.kubernetes.io/part-of=disaster-recovery-lab
python3 scripts/storage.py
bash scripts/v.sh restore create manual-dr --from-backup NOME_DO_BACKUP --namespace-mappings backup-demo:dr-notes --resource-modifier-configmap dr-restore-modifiers --include-cluster-resources=false --wait
bash scripts/v.sh restore describe manual-dr --details
bash scripts/k.sh -n velero get podvolumerestores
```

Confirme o PodVolumeRestore concluído, PVCs novos, cliente no nó novo e certificado do destino preservado. Leia os avisos do restore; não confunda ausência de erros com validação dos dados.

```bash
bash scripts/k.sh wait --for=condition=Ready pod/backup-client --timeout=180s
bash scripts/k.sh rollout status statefulset/postgres-alpine --timeout=240s
bash scripts/k.sh exec postgres-alpine-0 -- psql -U notes_admin -d notes -Atc "SELECT to_regclass('public.notes')"
```

O resultado da consulta deve ser vazio e a API deve ter zero réplicas. Somente nesse destino novo:

```bash
bash scripts/k.sh exec backup-client -- sh /scripts/restore.sh
bash scripts/k.sh scale deployment/notes-api --replicas=2
bash scripts/k.sh rollout status deployment/notes-api --timeout=180s
bash scripts/access.sh
```

O script de restore verifica o checksum antes de aplicar SQL em uma transação. Compare as notas pela API e pelo banco, além de schema, índices e sequência. O teste automatizado faz essas verificações e uma escrita controlada antes de considerar a recuperação concluída.

## Se o ensaio parar no meio

O snapshot privado `.local/source-recovery-private.json` registra as réplicas originais e os dados para comparação. `.local/network.json` identifica a única regra de bloqueio aplicada dentro do nó novo. `.local/source-recovery-result.json` informa se o bloco de recuperação encontrou erros.

```bash
python3 scripts/network.py clear
```

Esse comando remove apenas as duas regras deste lab para o IP e a porta registrados; não esvazia tabelas de rede. Se a origem de estudo continuar parada, restaure as réplicas de `backup-demo/notes-api`, `backup-demo/postgres-alpine` e `velero/velero` pelos valores do snapshot. Os padrões do ensaio local eram 2, 1 e 1; confira antes de usar.

Não altere `notes-lab` nem seu Argo CD para corrigir este ensaio. O código usa contextos explícitos, mas um comando manual sem kubeconfig pode atingir o cluster errado. Continue usando os wrappers deste projeto e do backup-restore-lab.

## Retorno da origem não é merge

O teste remove a escrita controlada no destino, desfaz o bloqueio e reabre as réplicas da origem para deixar os labs disponíveis. Em produção, escolha uma fonte autoritativa antes de liberar escritores e tráfego. Escritas feitas nos dois bancos depois do ponto do backup podem divergir; não há replicação ou reconciliação automática aqui. Não anunciamos troca de DNS ou de balanceador.

## Se o segundo nó não iniciar no WSL

O erro observado foi `Failed to create control group inotify object: Too many open files`. O kind documenta o limite compartilhado de inotify; não era falta de espaço nem corrupção do backup. No ambiente testado:

```bash
docker exec devops-notes-control-plane sysctl fs.inotify.max_user_instances
docker exec devops-notes-control-plane sysctl -w fs.inotify.max_user_instances=512
```

Esse parâmetro é compartilhado pelo kernel Docker/WSL e o ajuste é só de runtime. O valor anterior era 128. Não foi alterado um arquivo persistente de configuração. Os logs da criação devem ser conferidos antes de aplicar o mesmo diagnóstico em outro ambiente. [Referência do kind](https://kind.sigs.k8s.io/docs/user/known-issues/#pod-errors-due-to-too-many-open-files).
