# coletor

Consumidor Java instrumentado. É a única peça do experimento que conhece o Apache Kafka.
Traduz as notificações de `ConsumerRebalanceListener` em eventos de posse, conforme a
seção 6 de `notas/formalizacao.md` e a verificação da seção 7.

## Construção

Sem Maven nem Gradle. As dependências são baixadas do Maven Central com versões fixadas e
o código é compilado com `javac`.

```
./deps.sh       # lib/*.jar e lib/SHA256SUMS
./compilar.sh   # out/Coletor.class
```

Dependências: `kafka-clients` 4.3.2 e as quatro que seu POM declara em escopo runtime
(`zstd-jni` 1.5.6-10, `lz4-java` 1.11.4, `snappy-java` 1.1.10.11, `slf4j-api` 1.7.36),
mais `slf4j-simple` 1.7.36 para o log.

## Execução

```
./rodar.sh trabalhador=w1 protocolo=eager grupo=g1 topico=t1 saida=eventos-w1.csv
```

| Chave | Valor |
|---|---|
| `trabalhador` | identidade do processo; vira `client.id` |
| `protocolo` | `eager`, `cooperativo` ou `kip848` |
| `grupo`, `topico` | grupo de consumidores e tópico assinado |
| `saida` | arquivo CSV de eventos, aberto em modo de acréscimo |
| `bootstrap` | `localhost:9092` por padrão |
| `sessao_ms`, `heartbeat_ms` | 10000 e 3000 por padrão; só valem no protocolo clássico |
| `poll_ms` | tempo máximo de espera em `poll()`, 500 por padrão |
| `trabalho_ms` | tempo simulado de processamento por registro, 0 por padrão |

## Configuração por protocolo

| Protocolo | `group.protocol` | Atribuidor | Sessão e sinal de vida |
|---|---|---|---|
| eager | `classic` | `StickyAssignor` | cliente: `session.timeout.ms`, `heartbeat.interval.ms` |
| cooperativo | `classic` | `CooperativeStickyAssignor` | cliente, idem |
| kip848 | `consumer` | `group.remote.assignor=uniform` | servidor: `group.consumer.session.timeout.ms`, `group.consumer.heartbeat.interval.ms` (ver `ambiente/compose.yaml`) |

Os dois atribuidores clássicos compartilham o algoritmo de atribuição e diferem só no
protocolo de rebalanceamento; `uniform` é o equivalente do lado do servidor. A escolha
isola o protocolo do atribuidor.

`max.poll.interval.ms` fica no padrão de 300 s. Uma suspensão de 20 s ultrapassa a sessão
de 10 s sem atingir esse limite, então a exclusão ocorre pelo caminho de expiração de
sessão no coordenador, e não pelo de saída proativa da thread de sinal de vida.

## Saída

CSV `evento,trabalhador,particao,epoca,mono_ns,relogio_ns`, uma linha por partição
notificada. O instante monotônico é tomado uma vez no início de cada callback e repetido
nas linhas daquele callback.

| Evento | Origem | Uso |
|---|---|---|
| `atribuida` | `onPartitionsAssigned` | início de posse; a época registrada aqui é a do intervalo |
| `revogada` | `onPartitionsRevoked` | fim de posse, fechamento `revogada` |
| `perdida` | `onPartitionsLost` | fim de posse, fechamento `perdida` |
| `processo_inicio`, `processo_fim` | início e fim do processo | conferência da base de tempo com o orquestrador |

`mono_ns` é `System.nanoTime()`, que no HotSpot em Linux lê `CLOCK_MONOTONIC`, o mesmo
relógio de `time.monotonic_ns()` em Python. `relogio_ns` é `Instant.now()`. O orquestrador
compara os dois pares para medir o erro da base de tempo entre processos.

O encerramento por `SIGTERM` passa por `consumer.close()`, que dispara
`onPartitionsRevoked`. `SIGKILL` não gera evento: o orquestrador registra o instante e
fecha os intervalos abertos como `externo`.
