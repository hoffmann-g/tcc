#!/usr/bin/env bash
# Baixa as dependências do coletor do Maven Central para lib/, com versões fixadas.
# kafka-clients 4.3.2 declara as quatro primeiras em escopo runtime (POM de 4.3.2);
# slf4j-simple é a implementação de log usada aqui.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p lib

REPO=https://repo1.maven.org/maven2
ARTEFATOS=(
  org/apache/kafka/kafka-clients/4.3.2/kafka-clients-4.3.2.jar
  com/github/luben/zstd-jni/1.5.6-10/zstd-jni-1.5.6-10.jar
  at/yawk/lz4/lz4-java/1.11.4/lz4-java-1.11.4.jar
  org/xerial/snappy/snappy-java/1.1.10.11/snappy-java-1.1.10.11.jar
  org/slf4j/slf4j-api/1.7.36/slf4j-api-1.7.36.jar
  org/slf4j/slf4j-simple/1.7.36/slf4j-simple-1.7.36.jar
)

for caminho in "${ARTEFATOS[@]}"; do
  arquivo="lib/$(basename "$caminho")"
  if [[ -f "$arquivo" ]]; then
    echo "ok       $arquivo"
  else
    echo "baixando $arquivo"
    curl -fsSL -o "$arquivo" "$REPO/$caminho"
  fi
done

(cd lib && sha256sum ./*.jar > SHA256SUMS)
echo "somas em lib/SHA256SUMS"
