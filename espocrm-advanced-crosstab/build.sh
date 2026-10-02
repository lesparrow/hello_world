#!/usr/bin/env bash
# Builds the installable package: dist/advanced-crosstab-<version>.zip
set -euo pipefail
cd "$(dirname "$0")"
version=$(php -r 'echo json_decode(file_get_contents("manifest.json"))->version;')
mkdir -p dist
rm -f "dist/advanced-crosstab-${version}.zip"
zip -qr "dist/advanced-crosstab-${version}.zip" manifest.json files scripts
echo "dist/advanced-crosstab-${version}.zip"
