# A recuperação em outro cluster foi conferida

[English](validation.en.md) · Português

Passaram **32 testes locais**. A suíte levou 195 segundos; a aplicação recuperada ficou pronta 124 segundos após começar a instalação do Velero no destino. Esse intervalo inclui instalação, importação dos metadados, recuperação do volume e do SQL; não inclui criar o cluster nem guardar o kit. Não é um SLO.

Os clusters têm UIDs diferentes de kube-system, CAs diferentes e nós distintos. O novo nó não tinha o diretório de staging da origem. A localização de backup validou como ReadOnly; o Backup foi importado do S3, com outro UID, depois que a aplicação e o controlador de origem estavam parados. A sonda do destino não conseguia abrir conexão TCP com a API Kubernetes de origem.

O restore concluiu sem erros, com dois avisos. O PodVolumeRestore Kopia concluiu no nó novo. Os PVCs de dados e do dump têm UIDs diferentes dos da origem, e a classe de armazenamento foi alterada para dr-local-dump. O Secret voltou do backup e a CA do destino não foi sobrescrita.

As sete notas do backup voltaram com todos os campos, schema, índices e sequência conferidos. A oitava, posterior ao backup, permaneceu somente na origem. O destino aceitou uma escrita controlada, que foi removida, e manteve os dados após recriar o Pod do PostgreSQL. Tudo isso ocorreu antes de remover o bloqueio e religar a origem.

Depois, as oito notas e a sequência da origem continuaram idênticas ao snapshot anterior à interrupção. As réplicas e a conectividade foram restauradas, sem alterar imagem ou PVC da aplicação principal em notes-lab.

[Relatório completo](../evidence/verification.json) · [Backup importado](../evidence/imported-backup.json) · [Restore](../evidence/restore.json) · [Volume recuperado](../evidence/pod-volume-restores.json) · [Retorno da origem](../evidence/source-recovery-result.json).

## Os dois avisos

O PV local de origem não foi incluído entre os recursos de cluster. A consulta desse PV no arquivo do backup gera um aviso; o modificador remove a referência antiga e vincula o PVC a outro PV reservado no novo cluster. A recuperação foi comprovada por UID, localização, SHA-256, conteúdo e leitura pela aplicação.

O segundo aviso registra que kube-root-ca.crt já existe e difere do backup. Em outro cluster isso é esperado: a CA de destino é outra. O objeto gerado no destino foi mantido, e essa preservação foi testada. Os avisos continuam no [describe](../evidence/restore-description.txt) e no JSON de status.

## Limites e preparação

A origem não foi destruída. Interrompemos só os componentes do ambiente de backup e bloqueamos a API de origem dentro do nó de destino. O cluster principal permaneceu operando; não declaramos um teste de perda total do host ou failover de tráfego. O armazenamento S3 é comum e fica no mesmo computador.

A primeira criação do destino falhou porque systemd não conseguia criar uma instância inotify. Aumentamos o limite de 128 para 512 em runtime e repetimos a criação. O [registro do ajuste](../evidence/host-inotify.json) preserva o motivo e o escopo; não houve reinício dos labs antigos.
