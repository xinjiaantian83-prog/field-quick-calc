#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_NAME="SpriteAnchor"
DIST_DIR="dist"
ZIP_NAME="${APP_NAME}_mac.zip"

python3 -m PyInstaller --clean --noconfirm "${APP_NAME}.spec"

ditto -c -k --norsrc --keepParent \
  "${DIST_DIR}/${APP_NAME}.app" \
  "${DIST_DIR}/${ZIP_NAME}"

echo "Built ${DIST_DIR}/${APP_NAME}.app"
echo "Created ${DIST_DIR}/${ZIP_NAME}"
