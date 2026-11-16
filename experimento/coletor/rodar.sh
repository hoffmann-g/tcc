#!/usr/bin/env bash
# Executa um coletor à mão. O orquestrador não usa este script: monta o comando java
# diretamente para ser dono do PID. `exec` garante que o PID deste script seja o da JVM,
# para que SIGSTOP/SIGCONT/SIGTERM cheguem ao consumidor.
#
# Exemplo:
#   ./rodar.sh trabalhador=w1 protocolo=kip848 grupo=g1 topico=t1 saida=eventos-w1.csv
set -euo pipefail
cd "$(dirname "$0")"
LOG="${COLETOR_LOG:-coletor.log}"
exec java -cp "out:lib/*" \
  -Dorg.slf4j.simpleLogger.logFile="$LOG" \
  -Dorg.slf4j.simpleLogger.defaultLogLevel=info \
  -Dorg.slf4j.simpleLogger.showDateTime=true \
  -Dorg.slf4j.simpleLogger.dateTimeFormat="HH:mm:ss.SSS" \
  Coletor "$@"
