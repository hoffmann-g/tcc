#!/usr/bin/env bash
# Compila o coletor em out/. Requer lib/ preenchido por deps.sh.
set -euo pipefail
cd "$(dirname "$0")"
[[ -f lib/kafka-clients-4.3.2.jar ]] || ./deps.sh
rm -rf out
javac -Xlint:all -d out -cp "lib/*" src/Coletor.java
echo "compilado em out/"
