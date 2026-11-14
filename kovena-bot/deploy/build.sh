#!/usr/bin/env bash
# Собирает zip для Cloud Functions. requirements.txt Яндекс ставит сам.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f dist.zip
zip -qr dist.zip handler.py requirements.txt bot content db -x '*/__pycache__/*'
echo "dist.zip: $(du -h dist.zip | cut -f1)"
