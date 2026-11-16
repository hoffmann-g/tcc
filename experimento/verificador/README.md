# verificador

Decide exclusividade e calcula tempo órfão sobre um histórico de posse. Não depende do
Apache Kafka nem sabe qual protocolo produziu o histórico. Implementa as seções 4 e 6 de
`notas/formalizacao.md`.

## Entrada

CSV com cabeçalho e seis colunas:

| Coluna | Conteúdo |
|---|---|
| `trabalhador` | identidade do processo |
| `particao` | identidade da partição |
| `epoca` | época do membro no instante da notificação (`groupMetadata().generationId()`) |
| `inicio` | instante de `onPartitionsAssigned`, em ns de relógio monotônico |
| `fim` | instante do fechamento, em ns do mesmo relógio |
| `fechamento` | `revogada`, `perdida`, `externo` ou `janela` |

Cada linha é um intervalo de posse $(w, r, e, t_{ini}, t_{fim})$: o trabalhador $w$ se
considerou responsável pela partição $r$, sob a época $e$, durante $[t_{ini}, t_{fim})$.

Fechamentos: `revogada` é `onPartitionsRevoked`; `perdida` é `onPartitionsLost`;
`externo` é o instante em que o orquestrador matou o processo; `janela` é um intervalo
ainda aberto no fim da observação, fechado em $T_1$. Intervalos `janela` contam como
cobertura e não entram na detecção de sobreposição.

## Uso

```
uv run verificador historico.csv
uv run verificador historico.csv --margem 50000 --janela 0 120000000000 --json relatorio.json
uv run verificador historico.csv --particoes p0,p1,p2,p3,p4,p5,p6,p7
```

`--margem` é o erro da base de tempo entre processos, em ns. Sobreposições com duração
até esse valor não são reportadas. `--janela` fixa $[T_0, T_1)$; sem ela, a janela vai do
menor início ao maior fim. `--particoes` lista as partições do tópico, para que uma
partição que nunca foi coberta apareça como órfã na janela inteira.

Saída 0 quando as duas propriedades valem, 2 quando alguma é violada, 1 quando a entrada é
inválida.

## O que é calculado

**Exclusividade.** Para cada partição, pares de intervalos de trabalhadores distintos com
interseção de duração maior que a margem. Cada par é reportado com os dois trabalhadores,
as duas épocas, os dois fechamentos e o intervalo da interseção. Dois intervalos do mesmo
trabalhador nunca constituem violação.

**Disponibilidade.** Para cada partição, a união dos intervalos recortada à janela, e as
lacunas entre eles. O tempo órfão é a soma das lacunas. A partição satisfaz
disponibilidade na janela quando está coberta em $T_1$. A distribuição das lacunas
(quantidade, total, mediana, p90, máximo) é reportada em conjunto.

## Testes

```
uv run pytest
```

Os testes usam `verificador.sintetico`, que gera históricos ideais dos padrões eager e
cooperativo e planta sobreposições de duração conhecida. É a validação do verificador no
sentido 3 do plano: ele acusa o que foi plantado e nada além.
