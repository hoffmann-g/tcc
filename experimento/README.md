# experimento

Ambiente, coletor, orquestrador e verificador. Implementa o método da proposta: um traço
de churn independente do sistema é aplicado a um agrupamento Kafka real, os consumidores
instrumentados registram início e fim de posse por partição, e o verificador decide
exclusividade e calcula tempo órfão sobre o histórico resultante.

```
ambiente/       compose.yaml do broker (apache/kafka:4.3.2, KRaft, um nó)
coletor/        consumidor Java instrumentado; única peça que conhece o Kafka
orquestrador/   aplica o traço, registra os instantes, monta o histórico, chama o verificador
verificador/    exclusividade e tempo órfão sobre o histórico; não depende do Kafka
tracos/         traços de churn em TOML
execucoes/      uma pasta por execução, criada pelo orquestrador
```

## Fluxo

```
tracos/x.toml ──► orquestrador ──► coletor (×N, JVM no host) ──► eventos-w.csv
                       │                                              │
                       └── traco-executado.csv ─────► montagem ◄──────┘
                                                          │
                                                  historico.csv ──► verificador ──► relatorio.txt
```

## Preparação

```
docker compose -f ambiente/compose.yaml up -d      # broker; aguardar healthy
(cd coletor && ./deps.sh && ./compilar.sh)         # jars e Coletor.class
```

## Execução

```
cd orquestrador
uv run orquestrador validar  ../tracos/piloto.toml
uv run orquestrador executar ../tracos/piloto.toml --protocolo eager
uv run orquestrador executar ../tracos/piloto.toml --protocolo cooperativo
uv run orquestrador executar ../tracos/piloto.toml --protocolo kip848
```

Cada execução cria um tópico e um grupo novos, nomeados `<traço>-<protocolo>-<carimbo>`,
e grava em `execucoes/<mesmo nome>/`:

| Arquivo | Conteúdo |
|---|---|
| `execucao.json` | parâmetros, versões, T0 e T1 em ns monotônicos |
| `traco-executado.csv` | instante real de cada ação do orquestrador, com PID |
| `eventos-<w>.csv` | eventos de posse de cada coletor |
| `coletor-<w>.log`, `cliente-<w>.log` | saída do processo e log do cliente Kafka |
| `historico.csv` | o histórico de seis colunas, montado pelas regras da seção 6 |
| `montagem.json` | anomalias da montagem e desvio da base de tempo por coletor |
| `relatorio.txt`, `relatorio.json` | saída do verificador |

`uv run orquestrador montar execucoes/<pasta>` remonta o histórico e o relatório de uma
execução gravada, sem rodar nada no Kafka. `uv run orquestrador comparar execucoes/<a>
execucoes/<b> ... [--csv tabela.csv]` imprime uma tabela com uma linha por execução:
sobreposições, tempo órfão, distribuição das lacunas, intervalos abertos, anomalias e
erro da base de tempo. `uv run orquestrador figuras --linha-do-tempo <uma execução por
protocolo> --lacunas <execuções a acumular> [--saida DIR] [--sufixo=-nome]` gera as duas
figuras do volume em PNG e SVG: a linha do tempo de posse por partição, um painel por
protocolo, e a distribuição das lacunas de cobertura por protocolo. A saída padrão é
`volume-1/figuras/`.

## Decisões

- Broker `apache/kafka:4.3.2`, KRaft, um nó. O coordenador de grupo é um único broker e
  replicação não é objeto do trabalho.
- Os três protocolos no mesmo broker, escolhidos por cliente: eager é `classic` com
  `StickyAssignor`; cooperativo é `classic` com `CooperativeStickyAssignor`; KIP-848 é
  `consumer` com o atribuidor `uniform` do servidor. Os dois clássicos compartilham o
  algoritmo de atribuição e diferem só no protocolo; `uniform` é o equivalente do lado do
  servidor. Isso isola o protocolo do atribuidor.
- Tempo de sessão de 10 s e sinal de vida de 3 s nos três. No clássico são configuração
  do cliente; no KIP-848, do servidor, com o mínimo padrão de 45 s reduzido no broker.
- Consumidores como processos JVM no host, não em contêineres, para compartilharem o
  relógio monotônico do kernel com o orquestrador.
- Suspensão por `SIGSTOP`/`SIGCONT` no PID, por intervalo maior que o tempo de sessão.
- Sem sistema de build Java: dependências do Maven Central com versões fixadas e `javac`.

## Base de tempo

Coletores e orquestrador leem `CLOCK_MONOTONIC` do mesmo kernel: `System.nanoTime()` no
HotSpot em Linux e `time.monotonic_ns()` em Python. O orquestrador mede o desvio entre as
duas leituras em cada lançamento e usa o maior desvio como margem do verificador.
