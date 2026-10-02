#!/usr/bin/env bash
# Builds the installable EspoCRM extension: build/WalletPasses-<version>.zip
#
# Strategy for third-party libraries: they are installed with Composer at build time
# (runtime deps only: pkpass/pkpass, bacon/bacon-qr-code) into
#   files/custom/Espo/Modules/WalletPasses/vendor/
# and loaded by Resources/autoload.json ("autoloadFileList"). The target server needs neither
# Composer nor Internet access.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(php -r 'echo json_decode(file_get_contents("'"$ROOT"'/src/manifest.json"), true)["version"];')"
NAME="WalletPasses-${VERSION}"
BUILD="$ROOT/build"
STAGE="$BUILD/stage"
VENDOR_DIR="files/custom/Espo/Modules/WalletPasses/vendor"

if [[ "${1:-}" != "--skip-tests" ]]; then
    echo "> Running unit tests"
    (cd "$ROOT" && composer install --no-interaction --quiet && vendor/bin/phpunit --no-progress)
fi

echo "> Staging package"
rm -rf "$STAGE" "$BUILD/$NAME.zip"
mkdir -p "$STAGE"
cp -R "$ROOT/src/." "$STAGE/"

echo "> Installing runtime dependencies (no dev)"
mkdir -p "$BUILD/composer"
cp "$ROOT/build-config/composer.json" "$BUILD/composer/composer.json"
[[ -f "$ROOT/build-config/composer.lock" ]] && cp "$ROOT/build-config/composer.lock" "$BUILD/composer/composer.lock"
COMPOSER_VENDOR_DIR="$STAGE/$VENDOR_DIR" composer install \
    --working-dir="$BUILD/composer" --no-dev --no-interaction --no-progress --prefer-dist --optimize-autoloader
# Keep the lock file for reproducible builds.
cp "$BUILD/composer/composer.lock" "$ROOT/build-config/composer.lock"

echo "> Trimming vendor"
find "$STAGE/$VENDOR_DIR" -type d \( -iname tests -o -iname test -o -iname docs -o -iname .github -o -name .git \) -prune -exec rm -rf {} +
find "$STAGE/$VENDOR_DIR" -type f \( -name '*.md' -o -name 'phpunit*' -o -name '.gitignore' -o -name '.gitattributes' \) -delete

echo "> Linting PHP"
find "$STAGE/files/custom" "$STAGE/scripts" -name '*.php' -not -path '*/vendor/*' -print0 \
    | xargs -0 -n1 php -l > /dev/null

echo "> Creating $NAME.zip"
(cd "$STAGE" && zip -qr -X "$BUILD/$NAME.zip" manifest.json files scripts)
rm -rf "$STAGE" "$BUILD/composer"

echo "Done: $BUILD/$NAME.zip ($(du -h "$BUILD/$NAME.zip" | cut -f1))"
