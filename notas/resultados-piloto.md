# Resultados dos pilotos — 09/11/2026

Execuções em `experimento/execucoes/repeticoes/`: cinco do traço piloto e três do traço
de referência por protocolo, 24 no total, zero anomalias de montagem. Tabelas geradas
por `orquestrador comparar --agregar` (mediana [mínimo; máximo] entre execuções) e
gravadas em `execucoes/repeticoes/comparacao.csv`. As execuções em
`execucoes/rodada-unica/` são a rodada anterior, de uma execução por protocolo, feita
logo após a correção dos callbacks de coleção vazia.

Condições: broker `apache/kafka:4.3.2`, um nó; sessão de 10 s e sinal de vida de 3 s nos
três protocolos; 8 partições; sem produtor, então os consumidores não processam
registros e não há trabalho em curso a drenar nem posição a confirmar durante um
rebalanceamento.

## Traços

**Referência**: w1, w2 e w3 entram em t=0 e nada mais acontece em 60 s.

**Piloto**: 90 s. w1 e w2 entram em t=0; w3 entra em t=15; w2 é suspenso em t=30 por
20 s; w3 sai de forma ordenada em t=65; w1 é morto em t=75.

## Tabela agregada

| traço | protocolo | exec. | sobrep. por exec. | maior sobrep. (s) | órfão total (s) | lacunas por exec. | lacuna mediana (s) | lacuna máx (s) | erro base (µs) |
|---|---|---|---|---|---|---|---|---|---|
| piloto | eager | 5 | 3, 3, 3, 3, 3 | 9,783 [9,352; 9,886] | 59,4 [57,9; 66,1] | 45 [45; 53] | 0,021 [0,017; 0,032] | 10,39 [10,31; 10,81] | 87 |
| piloto | cooperativo | 5 | 3, 3, 3, 3, 3 | 9,912 [9,886; 9,961] | 80,5 [68,5; 81,3] | 23 [19; 23] | 2,992 [2,189; 3,005] | 10,24 [10,21; 10,29] | 36 |
| piloto | KIP-848 | 5 | 3, 3, 3, 3, 3 | 10,261 [9,970; 10,366] | 77,9 [65,8; 83,0] | 23 [23; 23] | 1,348 [1,136; 1,429] | 11,54 [9,01; 12,01] | 99 |
| referência | eager | 3 | 0, 0, 0 | — | 10,3 [10,0; 10,5] | 16 [16; 16] | 0,038 [0,032; 0,042] | 1,26 [1,22; 1,28] | 27 |
| referência | cooperativo | 3 | 0, 0, 0 | — | 24,3 [15,3; 24,5] | 13 [10; 13] | 1,156 [1,148; 1,174] | 3,02 [3,02; 3,02] | 37 |
| referência | KIP-848 | 3 | 0, 0, 0 | — | 24,4 [23,7; 29,3] | 13 [13; 16] | 1,180 [1,107; 1,200] | 3,00 [2,99; 3,12] | 67 |

## Exclusividade

Nas quinze execuções do piloto, o verificador acusou exatamente três sobreposições por
execução, uma por partição que w2 detinha no instante da suspensão. Em todas, um dos
intervalos é o de w2, fechado como `perdida`, e o outro é o do novo responsável, aberto
quando o coordenador redistribuiu as partições depois de expirar a sessão de w2. A maior
sobreposição por execução ficou entre 9,35 s e 10,37 s nos três protocolos; a sessão é de
10 s, e a diferença é o tempo entre a retomada de w2 e seu primeiro `poll()`, mais o
tempo que o coordenador leva para excluir e redistribuir.

Na referência não houve sobreposição em nenhuma execução.

A sequência observada é a prevista na seção 7.3 da formalização: congelamento em t=30;
expiração da sessão em t≈40; exclusão e redistribuição; início de posse nos novos
responsáveis; retomada em t=50; `onPartitionsLost` no primeiro `poll()`; fim de posse
de w2. A sobreposição é o intervalo entre o início de posse do novo responsável e essa
detecção.

Os três protocolos violam a exclusividade de posse sob a mesma condição e com a mesma
grandeza. O protocolo não altera esse resultado, porque a causa é comum aos três: a
detecção de falha é temporizada e o membro excluído não é notificado da exclusão. A
grandeza da violação é fixada pelo tempo de sessão, não pelo protocolo.

## Disponibilidade

Todas as partições estavam cobertas no fim da janela em todas as execuções.

**Forma.** O eager produz muitas lacunas curtas: 45 por execução, mediana de 21 ms. A
cada rebalanceamento todas as partições ficam órfãs pelo tempo da barreira, que aqui é
de dezenas de milissegundos porque não há processamento em curso a drenar nem posição a
confirmar. O cooperativo e o KIP-848 produzem poucas lacunas longas: 23 por execução,
com mediana por execução de 3,0 s e 1,35 s; reunindo as lacunas das cinco execuções,
como na figura, 2,26 s e 1,43 s. Só as partições transferidas ficam órfãs, mas cada
transferência espera que a revogação no antigo responsável seja confirmada ao coordenador
e que a atribuição chegue ao novo, e esse ciclo é pautado pelo sinal de vida, de 3 s.

**Mecanismo, visível na referência.** Com três trabalhadores entrando juntos, o eager
gasta 10,3 s de tempo órfão total: as oito partições ficam órfãs ~1,2 s até o primeiro
`poll()` depois da partida da JVM (8 × 1,26 s ≈ 10 s), e as dezesseis lacunas restantes,
dos dois rebalanceamentos seguintes, somam menos de 1 s. Os incrementais gastam ~24 s:
os mesmos ~10 s iniciais mais cinco transferências, porque o primeiro membro recebe as
oito partições e cinco delas migram para os outros dois, cada uma custando ~3 s
(5 × 3 s = 15 s). A lacuna máxima da referência é 1,26 s no eager e 3,0 s nos
incrementais, e a lacuna mediana do cooperativo, 2,99 s no piloto e 1,16 s na
referência, é o próprio intervalo do sinal de vida ou sua metade.

**Total.** No piloto, o tempo órfão total mediano é 59,4 s no eager, 80,5 s no
cooperativo e 77,9 s no KIP-848. As lacunas de ~10 s causadas pela sessão do trabalhador
suspenso e do trabalhador morto são comuns aos três (lacuna máxima entre 10,2 s e 11,5 s
em todos). A diferença de ~20 s entre eager e incrementais é o custo acumulado das
transferências pautadas pelo sinal de vida. As amplitudes entre execuções se sobrepõem
pouco: eager [57,9; 66,1] contra cooperativo [68,5; 81,3] e KIP-848 [65,8; 83,0].

## Leitura contra a hipótese

A hipótese da seção 5.4 da formalização diz que reduzir a sincronização global reduz o
tempo órfão e amplia a janela de sobreposição. Nestas condições, nenhuma das duas partes
se confirma.

A janela de sobreposição foi a mesma nos três protocolos, porque o cenário que a produz,
suspensão acima da sessão, é dominado pelo tempo de sessão. O protocolo decide quando o
novo responsável assume depois da exclusão, mas a exclusão em si e a detecção pelo membro
excluído não dependem dele.

O tempo órfão foi maior nos protocolos incrementais, e não menor, porque o custo da
barreira do eager é pequeno quando os trabalhadores não têm processamento em curso, e o
custo de cada transferência incremental é um ciclo de sinal de vida. A hipótese presume
que a barreira é cara; ela é cara quando há trabalho a drenar e posição a confirmar, o
que este piloto não tem.

Isso define a campanha de TCC II: variar o intervalo do sinal de vida e a carga de
processamento. A expectativa é que o custo da barreira cresça com a carga e o das
transferências incrementais caia com o intervalo, e que exista um cruzamento. A
divergência entre o modelo e estas medições é resultado, não erro: ela diz quais
parâmetros a hipótese omitiu.

## Base de tempo

O desvio entre o relógio monotônico lido pelo coletor e pelo orquestrador ficou abaixo
de 100 µs em todos os 72 lançamentos, sempre negativo, o que indica custo fixo de
leitura e não deriva. É cinco ordens de grandeza menor que as sobreposições. O maior
desvio de cada execução foi usado como margem do verificador.

## Figuras

`volume-1/figuras/linha-do-tempo-piloto.png`: histórico de posse das oito partições na
rodada única de 09/11 (`execucoes/rodada-unica/`), um painel por protocolo.
`volume-1/figuras/lacunas-piloto.png`: duração de cada lacuna de cobertura nas quinze
execuções do piloto, por protocolo, em escala logarítmica.

## Limitações

1. Sem produtor: a posse é medida, os efeitos externos durante a sobreposição não. Um
   produtor com carga e um registro de efeitos por partição permitiriam contar as
   operações executadas fora da posse, e dariam à barreira do eager o custo que ela tem
   em produção.
2. Um único intervalo de sinal de vida (3 s) e um único tempo de sessão (10 s). O
   resultado de disponibilidade depende do primeiro; o de exclusividade, do segundo.
3. Os atribuidores diferem entre o clássico e o KIP-848 (`Sticky` e `uniform`), embora
   compartilhem o critério de atribuição.
4. A máquina hospeda broker e consumidores. O ruído foi caracterizado pela referência,
   não controlado.
5. Cinco execuções por configuração. Suficiente para a amplitude; não para inferência.
