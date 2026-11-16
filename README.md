# TCC — Rebalanceamento de grupos de consumidores no Apache Kafka

Guilherme Hoffmann. Orientador: Fernando Luis Dotti. TCC I em 2026/2.

Formalizar a atribuição de partições a consumidores como comunicação em grupo com
sincronia de visão, e comparar empiricamente os três protocolos de rebalanceamento do
Apache Kafka — eager, cooperativo (KIP-429) e KIP-848 — medindo tempo órfão por partição
e sobreposição de posse.

## Estado em 09/11/2026

A proposta foi entregue na semana 5 e devolvida com anotações do orientador em 13/10. O
volume final de TCC I vence em 30/11, fim da semana 16.

Feito até 09/11: proposta entregue; triagem dos comentários do orientador; formalização
do modelo com as quatro questões em aberto respondidas e verificadas no código do cliente
Java; ambiente, coletor, orquestrador e verificador implementados e testados; traços de
referência e piloto executados nos três protocolos, com a cadeia funcionando de ponta a
ponta e a sobreposição de posse após suspensão observada nos três; referências pendentes
reunidas; rascunho completo do volume em `volume-1/volume.md`, com todas as seções
redigidas e as pendências marcadas entre colchetes; cinco repetições do piloto e três da
referência por protocolo, sem anomalias; as duas figuras do volume geradas. Resultado
central em `notas/resultados-piloto.md`: a sobreposição de posse é igual nos três
protocolos e fixada pelo tempo de sessão; o tempo órfão é maior nos incrementais, porque
cada transferência custa um ciclo de sinal de vida.

Não feito: validação da formalização com o orientador; revisão do rascunho pelo autor;
transposição para o modelo da disciplina e PDF; busca sistemática em ACM DL e IEEE Xplore
para a seção de trabalhos relacionados.

Avaliador: prof. Michael da Costa Mora.

## Organização

```
proposta/      a entrega da semana 5 e a devolução comentada
notas/         formalização do modelo e resultados do piloto
experimento/   ambiente (broker), coletor (Java), orquestrador e verificador (Python), traços, execuções
volume-1/      volume final de TCC I: volume.md (rascunho) e referencias.bib
```

### notas/

| Arquivo | Conteúdo |
|---|---|
| [formalizacao.md](notas/formalizacao.md) | Modelo de visões, posse, exclusividade e disponibilidade, sua instanciação no Kafka e a verificação das definições no código do cliente Java |
| [resultados-piloto.md](notas/resultados-piloto.md) | Resultados dos pilotos de 09/11, com tabela agregada e leitura contra a hipótese |

### proposta/

| Arquivo | Conteúdo |
|---|---|
| `proposta-entregue.pdf` | A versão entregue, 14 páginas. É a referência do que foi submetido |
| `proposta-comentada.pdf` | A devolução do orientador, 16 páginas, com as anotações |

## Vocabulário

Fechado em [notas/formalizacao.md](notas/formalizacao.md) e de uso obrigatório em todo o
texto, porque a maior parte dos comentários do orientador decorre de ele não estar fechado:
partição, trabalhador, membro, consumidor, operar, posse, exclusividade, barreira,
rebalanceamento. Trabalhador é o termo do modelo; consumidor, só quando se fala do Kafka;
membro, só quando se fala da composição do grupo. Rebalanceamento substitui transição.
