# Formalização do modelo de visões e propriedades

Documento de trabalho da atividade 4 do cronograma. Alimenta a seção 3.2 do volume final
de TCC I e responde aos comentários 1, 2, 3, 9, 10, 12, 15, 16 e 17 do orientador sobre
a proposta, numerados na ordem em que aparecem em `proposta/proposta-comentada.pdf`. A
seção 7 registra a verificação das definições no código do
cliente Java, feita em 09/11/2026.

O objetivo é fixar o vocabulário antes de instrumentar qualquer coisa. O modelo define o
que é partição, responsável, posse e exclusividade sem mencionar o Apache Kafka. O Kafka
é instanciado nele em seguida.

## 1. Vocabulário

**Recurso particionado.** Um recurso particionado é um recurso cujo conteúdo foi dividido
previamente, pelo projetista do sistema, em um número fixo de partes disjuntas. A divisão
é dada, e não é decidida em tempo de execução. O que se decide em tempo de execução é
quem opera cada parte.

Essa distinção responde ao comentário 1. Não se trata de particionar carga de trabalho:
trata-se de atribuir partes já definidas a processos. O número de partes não muda durante
a execução; o conjunto de processos, sim.

**Partição.** Cada uma dessas partes. Formalmente, um elemento de um conjunto finito $R$,
fixo durante toda a execução. Uma partição é uma unidade de exclusão mútua: a divisão
existe para que operações sobre partes distintas possam ocorrer em paralelo sem
coordenação, e operações sobre a mesma parte não possam.

**Trabalhador.** Um processo capaz de operar sobre partições. O conjunto de trabalhadores
que existem em um dado instante varia ao longo da execução. $W$ denota o conjunto de
todos os trabalhadores que existem em algum instante da execução.

O termo trabalhador é usado no modelo. Consumidor é usado apenas quando se fala do Apache
Kafka, e membro apenas quando se fala da composição de um grupo. Os três não são
intercambiáveis. Isso responde ao comentário 15.

**Operar sobre uma partição.** Executar, sobre o conteúdo da partição, operações que
produzem efeitos observáveis fora do trabalhador. O efeito pode ser interno ao sistema
particionado, como registrar o avanço da leitura, ou externo a ele, como uma escrita em
outro banco de dados ou uma chamada a um serviço. A distinção entre esses dois tipos de
efeito é central e retorna na seção 4.

Isso responde aos comentários 9 e 16. "Consumir uma partição" é vago porque não diz o que
acontece com o que foi lido. O modelo fala em operar, e distingue os efeitos pelo alcance
do mecanismo de proteção do sistema.

**Responsável.** O trabalhador que detém, em um dado instante, o direito de operar sobre
uma dada partição.

## 2. Visões e execução

Uma **visão** é uma tripla $v = (e, M, a)$:

- $e \in \mathbb{N}$, a **época**, identificador da visão;
- $M \subseteq W$, o conjunto de **membros**, os trabalhadores que o sistema considera
  vivos na visão;
- $a : R \to M \cup \{\bot\}$, a **atribuição**, que associa a cada partição um membro ou
  nenhum.

Uma **execução** é uma sequência de visões $v_0, v_1, v_2, \ldots$ com épocas
estritamente crescentes. A passagem de $v_i$ para $v_{i+1}$ é um **rebalanceamento**.

O termo rebalanceamento substitui transição em todo o texto, conforme o comentário 8.

A atribuição é uma decisão do sistema. Ela não diz o que cada trabalhador acredita, e não
diz o que cada trabalhador faz. Essa separação é o ponto do modelo.

## 3. Posse

A atribuição é global e instantânea: na visão $v_i$, a partição $r$ pertence a $a_i(r)$.
A realidade observável não é essa. Um trabalhador só começa a operar sobre $r$ depois de
descobrir que $r$ lhe foi atribuída, e só para de operar depois de descobrir que $r$ lhe
foi retirada. Entre a decisão do sistema e o conhecimento do trabalhador há um intervalo,
e é dentro dele que as propriedades de interesse são violadas ou preservadas.

A **posse** é o que se mede. Um **intervalo de posse** é uma tupla

$$(w, r, e, t_{\text{ini}}, t_{\text{fim}})$$

que afirma: o trabalhador $w$ se considerou responsável pela partição $r$, sob a época
$e$, durante o intervalo $[t_{\text{ini}}, t_{\text{fim}})$. O início é o instante em que
$w$ passa a estar apto a operar sobre $r$; o fim é o instante em que $w$ deixa de estar
apto, seja por revogação ordenada, seja por constatação de perda.

Um **histórico** $H$ é um conjunto de intervalos de posse. O histórico é o objeto sobre o
qual as duas propriedades são enunciadas, e é a entrada do verificador.

Posse é uma propriedade do trabalhador, não do sistema. Dois trabalhadores podem se
considerar responsáveis pela mesma partição ao mesmo tempo sem que nenhuma visão jamais
tenha atribuído a partição a dois membros. É exatamente essa diferença que o trabalho
mede.

## 4. As duas propriedades

### 4.1 Exclusividade

Um histórico $H$ satisfaz **exclusividade** quando, para quaisquer dois intervalos de
posse $(w_1, r, e_1, s_1, f_1)$ e $(w_2, r, e_2, s_2, f_2)$ em $H$ com $w_1 \neq w_2$, os
intervalos $[s_1, f_1)$ e $[s_2, f_2)$ são disjuntos.

A violação é observável como sobreposição, e tem grandeza: a duração
$\min(f_1, f_2) - \max(s_1, s_2)$ da interseção. A sobreposição é definida sobre a
partição e sobre dois trabalhadores distintos; dois intervalos do mesmo trabalhador em
épocas diferentes não constituem violação.

Isso responde ao comentário 2. Exclusividade, aqui, é exclusividade de posse: no máximo
um trabalhador responsável por partição a cada instante. Não é exclusão mútua sobre uma
operação, e não é unicidade da atribuição.

### 4.2 Disponibilidade

Para uma partição $r$ e um instante $t$, $r$ está **coberta** em $t$ quando existe em $H$
um intervalo de posse $(w, r, e, s, f)$ com $t \in [s, f)$. Caso contrário, $r$ está
**órfã** em $t$.

O **tempo órfão** de $r$ em uma janela de observação $[T_0, T_1)$ é a medida do conjunto
$\{t \in [T_0, T_1) : r \text{ está órfã em } t\}$.

Um histórico satisfaz **disponibilidade** quando o tempo órfão de toda partição é finito,
o que em uma execução limitada equivale a exigir que toda partição volte a ser coberta
antes do fim da janela.

O tempo órfão é definido sobre a partição, e não sobre o grupo. É isso que o torna
comparável entre protocolos. Um protocolo que para o grupo inteiro e um protocolo em que
cada trabalhador reconcilia seu estado isoladamente produzem históricos de formas
diferentes, mas o tempo órfão de uma partição é calculado da mesma maneira nos dois. A
grandeza usualmente reportada, tempo de rebalanceamento, não tem essa propriedade: ela
pressupõe um evento global com início e fim, que no terceiro protocolo não existe.

### 4.3 Por que as duas estão em oposição

Encurtar o intervalo entre a revogação em um trabalhador e a atribuição em outro reduz o
tempo órfão e aumenta a janela de sobreposição. Ampliá-lo faz o contrário. A barreira
global é o mecanismo que garante exclusividade ao custo de tempo órfão; retirá-la reduz o
tempo órfão e transfere para o mecanismo de cercamento a responsabilidade pela
exclusividade.

## 5. Instanciação no Apache Kafka

### 5.1 Correspondência

| Modelo | Apache Kafka |
|---|---|
| Partição | Partição de tópico |
| Trabalhador | Consumidor de um grupo |
| Conjunto de membros $M$ | Composição do grupo, mantida pelo coordenador |
| Época $e$ | Geração do grupo no protocolo clássico; época de atribuição no KIP-848. O intervalo de posse registra a época do membro, lida em `groupMetadata().generationId()` (seção 7.1) |
| Atribuição $a$ | Atribuição de partições a membros |
| Rebalanceamento | Rebalanceamento |
| Início de posse | Notificação de partições atribuídas |
| Fim de posse | Notificação de partições revogadas ou perdidas |

### 5.2 Quais garantias de sincronia de visão o Kafka oferece

Esta subseção responde ao comentário 12. As propriedades de group membership seguem a
organização de Chockler, Keidar e Vitenberg.

**Acordo sobre a sequência de visões.** A especificação clássica exige que membros que
instalam visões consecutivas instalem a mesma visão. No Kafka, a composição é decidida
por um único processo, o coordenador do grupo, que é um broker designado. Não há consenso
entre os membros. O coordenador é um sequenciador: a sequência de visões existe e é
única, porque há uma única fonte que a produz. Nesse sentido restrito, o acordo é trivial
e vale.

**Instalação simultânea.** A especificação clássica não exige simultaneidade, mas a
sincronia virtual exige que a entrega de mensagens seja consistente com a sequência de
visões. É aqui que o Kafka se afasta. Os membros aprendem a nova visão em instantes
distintos, e nada impede que um membro continue operando sob uma visão que já foi
substituída. No protocolo eager isso é limitado pela barreira; nos protocolos
incrementais, não.

**Detecção de saída.** É temporizada, baseada em sinal periódico de vida e em um intervalo
de sessão configurado. Um membro lento e um membro falho são indistinguíveis para o
coordenador, situação caracterizada por Chandra e Toueg. A consequência é que a exclusão
de um membro da composição pode ocorrer enquanto o membro continua em execução e ainda se
considera responsável por suas partições.

**Cercamento.** A época é anexada às requisições, e o coordenador rejeita requisições que
apresentem época desatualizada. O alcance desse mecanismo é restrito: ele protege as
operações dirigidas ao próprio Kafka, em particular a confirmação da posição de leitura.
Operações que não passam pelo Kafka não são alcançadas.

**Enunciado preciso da garantia.** O Apache Kafka garante exclusividade sobre as
operações cercadas, e não sobre os intervalos de posse. Um membro excluído do grupo sem
ter percebido pode operar sobre suas partições e produzir efeitos externos durante todo o
intervalo entre sua exclusão e sua primeira requisição rejeitada. Essa é a formulação
verificável da afirmação destacada pelo orientador no comentário 18.

### 5.3 Os três protocolos como padrões de rebalanceamento

Os três protocolos diferem em como os trabalhadores passam da atribuição $a_i$ para
$a_{i+1}$.

**Eager.** Todo membro encerra a posse de todas as suas partições antes que a nova
atribuição seja calculada. Entre o encerramento e a nova atribuição, nenhuma partição
está coberta, independentemente de quantas mudaram de responsável. A barreira global é
esse ponto de sincronização: o cálculo da nova atribuição não começa antes que todos os
membros tenham confirmado o encerramento.

**Cooperativo, KIP-429.** Cada membro encerra a posse apenas das partições que a nova
atribuição transfere para outro membro, e mantém as demais. Como o novo responsável só
inicia a posse depois que o anterior a encerrou, o procedimento pode exigir mais de uma
rodada. O tempo órfão fica restrito às partições efetivamente transferidas.

**KIP-848.** O cálculo da atribuição passa do membro para o coordenador, e cada membro
recebe sua atribuição-alvo junto ao sinal periódico de vida, reconciliando seu estado de
forma independente dos demais. Deixa de existir um ponto de sincronização global.

A barreira a que o comentário 17 se refere é a do protocolo eager, o ponto de
sincronização descrito acima. O KIP-848 elimina tanto a barreira do eager quanto o
encadeamento de rodadas do cooperativo.

### 5.4 Hipótese que o experimento testa

Reduzir a sincronização global reduz o tempo órfão e amplia a janela em que a posse de
uma mesma partição pode se sobrepor. A hipótese é uma consequência do modelo; as medições
no Apache Kafka a sustentam ou a refutam.

## 6. Do modelo ao verificador

O histórico $H$ é o formato de entrada do verificador: um conjunto de tuplas
$(w, r, e, t_{\text{ini}}, t_{\text{fim}})$. O formato não faz referência a nenhum
sistema. O verificador decide exclusividade por detecção de sobreposições e calcula a
distribuição do tempo órfão por partição. Ele não precisa saber qual protocolo produziu o
histórico.

A instrumentação tem uma única obrigação: traduzir os pontos de notificação do sistema
sob observação em instantes de início e fim de posse, conforme a seção 3. Para o Apache
Kafka, isso significa registrar as notificações de partições atribuídas, revogadas e
perdidas.

**Base de tempo.** Os intervalos são registrados por processos distintos, e a comparação
exige base comum. Os consumidores executam em uma mesma máquina, com relógio monotônico
compartilhado. O erro residual é medido e reportado junto aos resultados, e sobreposições
de duração inferior à margem de erro não são reportadas como violação.

**Regras de fechamento do intervalo.** Decorrem da verificação da seção 7.3.

1. $t_{\text{ini}}$ é o instante de `onPartitionsAssigned`, registrado por partição.
2. $t_{\text{fim}}$ é o instante de `onPartitionsRevoked` ou de `onPartitionsLost`,
   registrado por partição, com indicação de qual dos dois ocorreu.
3. Para um trabalhador encerrado pelo orquestrador sem oportunidade de callback,
   $t_{\text{fim}}$ de todos os seus intervalos abertos é o instante do envio do sinal,
   registrado pelo orquestrador no traço. O fechamento é marcado como externo.
4. Intervalos ainda abertos no fim da janela de observação são fechados em $T_1$ e
   reportados separadamente, sem entrar no cálculo de sobreposição.
5. A época do intervalo é `groupMetadata().generationId()` lida dentro de
   `onPartitionsAssigned`. Nos callbacks de fim ela não serve: quando `onPartitionsLost`
   roda, a geração já foi zerada no clássico (`NO_GENERATION`, valor −1) e a época do
   membro já foi reposta a 0 no KIP-848 (`resetEpoch` precede `signalPartitionsLost`).

O histórico ganha, portanto, um sexto campo: o tipo de fechamento, com valores
*revogada*, *perdida*, *externo* e *janela*.

## 7. Verificação no cliente Java

As quatro questões deixadas em aberto na versão anterior desta seção foram verificadas em
09/11/2026 na página do KIP-848, no Javadoc de `ConsumerRebalanceListener` do Kafka 4.0 e
no código do cliente Java em `trunk`: `ConsumerCoordinator`, `AbstractCoordinator`,
`AbstractMembershipManager`, `ConsumerMembershipManager`, `AsyncKafkaConsumer` e
`FetchCollector`. As consequências já estão incorporadas às seções 5 e 6.

### 7.1 Épocas no KIP-848

O KIP-848 define três contadores distintos.

- **Época do grupo.** Incrementada pelo coordenador sempre que uma nova atribuição se
  torna necessária: mudança na composição, na assinatura ou nos metadados das partições,
  ou exclusão de um membro.
- **Época de atribuição.** A época do grupo usada para calcular a atribuição-alvo. É
  fixada quando o coordenador calcula a atribuição e converge para a época do grupo.
- **Época do membro.** A época da atribuição que o membro usa no momento. É a época
  anexada às requisições e usada para cercamento, em particular na confirmação da posição
  de leitura. Membros distintos podem estar em épocas distintas no mesmo instante.

No modelo, o $e$ da visão $v = (e, M, a)$ é a época de atribuição, porque é sob ela que
$a$ foi calculada. O $e$ do intervalo de posse é a época do membro no instante da
notificação, porque o intervalo registra o que o trabalhador acredita. No protocolo
clássico os dois coincidem na geração do grupo. No KIP-848 podem diferir, e a diferença é
observável: um membro operando sob época $e_w$ enquanto a atribuição vigente tem época
$e > e_w$ é um membro com conhecimento defasado.

Nos protocolos incrementais, uma partição mantida através de rebalanceamentos sucessivos
não gera nova notificação de atribuição, e o intervalo de posse conserva a época em que
foi aberto, ainda que a geração do grupo ou a época do membro tenham avançado. O intervalo
registra a época da atribuição, não a época corrente. Nos pilotos de 09/11 isso aparece
no protocolo cooperativo: um trabalhador que entrou na geração 1 e manteve suas partições
por cinco rebalanceamentos fechou os intervalos com $e = 1$.

A aplicação lê a época do membro em `consumer.groupMetadata().generationId()`. No
consumidor novo, `AsyncKafkaConsumer.updateGroupMetadata` escreve a época do membro nesse
campo quando `MemberStateListener.onMemberEpochUpdated` dispara. Isso ocorre na thread de
fundo, ao receber a resposta do sinal de vida, antes de o evento de atribuição ser
processado na thread da aplicação. Dentro de `onPartitionsAssigned`, o valor lido já é a
nova época. No consumidor clássico, o campo é a geração do grupo.

### 7.2 Início de posse e primeiro registro

O Javadoc de `onPartitionsAssigned` afirma que o método é chamado depois que a
reatribuição termina e antes que o consumidor comece a buscar dados, e só como resultado
de uma chamada a `poll()`. O código confirma nos dois consumidores.

No clássico, o callback roda em `ConsumerCoordinator.onJoinComplete`, dentro da
atualização de metadados que `poll()` executa antes de buscar registros. No novo,
`AsyncKafkaConsumer.poll()` processa os eventos da thread de fundo em
`processBackgroundEvents` antes de `pollForFetches`; o evento de atribuição aplica a nova
atribuição e executa o callback de forma síncrona na thread da aplicação. `collectFetch`
retém registros em buffer enquanto há reconciliação pendente, e o membro só confirma a
nova atribuição ao coordenador, por sinal de vida, depois que o callback termina.

O instante registrado dentro de `onPartitionsAssigned` é anterior ao primeiro registro
daquela partição entregue à aplicação. O requisito da seção 3 é atendido.

### 7.3 Fim de posse: caminhos de exclusão

Os caminhos pelos quais um consumidor perde partições, com o callback que cada um dispara.

Protocolo clássico (`ConsumerCoordinator`, `AbstractCoordinator`):

| Caminho | Mecanismo | Callback |
|---|---|---|
| Rebalanceamento | `onJoinPrepare` (eager: todas as partições, no início) ou `onJoinComplete` (cooperativo: só as transferidas, no fim) | `onPartitionsRevoked` |
| Expiração de sessão no coordenador | O próximo sinal de vida recebe `UNKNOWN_MEMBER_ID` ou `ILLEGAL_GENERATION`; `resetStateOnResponseError` zera a geração; no próximo `poll()`, `onJoinPrepare` registra "Giving away all assigned partitions as lost since generation/memberID has been reset" | `onPartitionsLost` |
| Expiração de `max.poll.interval.ms` | A thread de sinal de vida executa `handlePollTimeoutExpiry` e `maybeLeaveGroup`, envia `LeaveGroup` e zera a geração em `resetGenerationOnLeaveGroup`; no próximo `poll()`, `onJoinPrepare` | `onPartitionsLost` |
| `close()` ou `unsubscribe()` | `onLeavePrepare` | `onPartitionsRevoked`; `onPartitionsLost` se a geração estiver zerada ou houver rebalanceamento em curso |
| Morte do processo | — | nenhum |

KIP-848 (`AbstractMembershipManager`, `ConsumerMembershipManager`, `AsyncKafkaConsumer`):

| Caminho | Mecanismo | Callback |
|---|---|---|
| Rebalanceamento | `maybeReconcile`, `revokePartitions`, `assignPartitions`; o coordenador só entrega a partição ao novo membro depois que o anterior confirma a revogação | `onPartitionsRevoked`, depois `onPartitionsAssigned` no novo responsável |
| Expiração de sessão, época defasada ou revogação não confirmada dentro do tempo de rebalanceamento | O sinal de vida recebe `UNKNOWN_MEMBER_ID` ou `FENCED_MEMBER_EPOCH`; `transitionToFenced`, `signalPartitionsLost`, `clearAssignment`, `transitionToJoining` com época 0 | `onPartitionsLost` |
| Expiração do temporizador de `poll()` | `transitionToSendingLeaveGroup(true)` sai com época negativa; `transitionToStale` e `signalPartitionsLost`; `maybeRejoinStaleMember` no próximo `poll()` | `onPartitionsLost` |
| `close()` | `AsyncKafkaConsumer.close()` decide pelo valor de `generationId()` | `onPartitionsRevoked` se maior que zero, senão `onPartitionsLost` |
| Erro fatal | `transitionToFatal` | `onPartitionsLost`, exceto se o membro já estava saindo |
| Morte do processo | — | nenhum |

Em todos os caminhos em que o processo continua existindo há notificação. O único caminho
sem notificação é a morte do processo, que o orquestrador provoca e portanto observa. A
questão 3 não descreve um risco de instrumentação; descreve uma regra de fechamento, que
é a regra 3 da seção 6.

Duas consequências.

A primeira: o fim de posse registrado por `onPartitionsLost` é o instante da detecção, não
o da exclusão pelo coordenador. A detecção exige que a thread da aplicação chame `poll()`
depois que a thread de fundo recebeu o erro. Entre a exclusão e a detecção, o trabalhador
se considera responsável, e isso é posse pela definição da seção 3. Para um trabalhador
suspenso, a sequência é: congelamento; expiração da sessão; exclusão pelo coordenador;
reatribuição das partições; início de posse no novo responsável; descongelamento; término
do processamento do lote obtido antes do congelamento; `poll()`; `onPartitionsLost`; fim
de posse. A sobreposição entre o início de posse do novo responsável e esse fim de posse
é a violação que o experimento procura.

A segunda: depois do callback, nenhum registro de uma partição perdida é entregue.
`FetchCollector.fetchRecords` descarta buscas concluídas de partições que não estão mais
atribuídas, com a mensagem "Not returning fetched records for partition {} since it is no
longer assigned". Registros obtidos por um `poll()` anterior à perda podem ser
processados pela aplicação depois da exclusão, mas antes do fim de posse, o que é
consistente com a definição.

### 7.4 Referências para a atribuição no coordenador

Para o comentário 10, a fonte primária é a página do KIP-848, que afirma que "the group
coordinator either directly computes the new target assignment" por meio de um atribuidor
do lado do servidor, e que atribuidores do lado do cliente não foram implementados. O
anúncio de lançamento do Apache Kafka 4.0.0, de 18/03/2025, registra a disponibilidade
geral do protocolo, habilitado por padrão no servidor, com adesão do cliente por
`group.protocol=consumer`.

Fonte secundária: Lacefield, blog da Confluent, 03/06/2025. Descreve a migração do cálculo
da atribuição do cliente para o coordenador e lista as configurações de cliente que o novo
protocolo ignora (`partition.assignment.strategy`, `session.timeout.ms`,
`heartbeat.interval.ms`) e suas substitutas no servidor
(`group.consumer.session.timeout.ms`, `group.consumer.heartbeat.interval.ms`), com os
atribuidores `uniform` e `range`.

O KIP-1251 documenta uma consequência da separação entre época de atribuição e época do
membro: uma confirmação de posição válida pode ser rejeitada porque a partição foi
atribuída em época posterior à do membro. Serve como evidência de que os três contadores
da seção 7.1 são distintos na prática.

### Fontes

- KIP-848: <https://cwiki.apache.org/confluence/display/KAFKA/KIP-848%3A+The+Next+Generation+of+the+Consumer+Rebalance+Protocol>
- KIP-1251: <https://cwiki.apache.org/confluence/display/KAFKA/KIP-1251%3A+Assignment+epochs+for+consumer+groups>
- Javadoc `ConsumerRebalanceListener`, Kafka 4.0: <https://kafka.apache.org/40/javadoc/org/apache/kafka/clients/consumer/ConsumerRebalanceListener.html>
- Anúncio do Apache Kafka 4.0.0: <https://kafka.apache.org/blog/2025/03/18/apache-kafka-4.0.0-release-announcement/>
- Lacefield, J. KIP-848: A New Consumer Rebalance Protocol for Apache Kafka 4.0. Confluent, 03/06/2025: <https://www.confluent.io/blog/kip-848-consumer-rebalance-protocol/>
- Código do cliente, `apache/kafka` em `trunk`, pacote `org.apache.kafka.clients.consumer.internals`: `ConsumerCoordinator.java`, `AbstractCoordinator.java`, `AbstractMembershipManager.java`, `ConsumerMembershipManager.java`, `AsyncKafkaConsumer.java`, `FetchCollector.java`.
