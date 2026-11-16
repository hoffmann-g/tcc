# orquestrador

Aplica um traço de churn a um agrupamento Kafka, monta o histórico de posse a partir dos
eventos dos coletores e chama o verificador. Uso e formato das saídas em
`../README.md`.

```
uv run orquestrador validar  TRACO.toml
uv run orquestrador executar TRACO.toml --protocolo eager|cooperativo|kip848
uv run orquestrador montar   PASTA_DA_EXECUCAO
uv run orquestrador comparar PASTAS... [--agregar] [--csv ARQUIVO]
uv run orquestrador figuras  --linha-do-tempo PASTAS... --lacunas PASTAS...
uv run pytest
```
