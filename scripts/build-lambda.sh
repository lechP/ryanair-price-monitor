#!/usr/bin/env bash
# Build dist/lambda.zip for the Python 3.12 arm64 Lambda runtime.
# Runtime dependencies come from uv.lock; dev dependencies (pytest, boto3) are left out
# because boto3 is already provided by the Lambda runtime.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

package_dir=build/package
rm -rf build dist
mkdir -p "$package_dir/config" dist

uv export --frozen --no-dev --no-hashes --no-emit-project --format requirements-txt > build/requirements.txt
uv pip install \
  --quiet \
  --target "$package_dir" \
  --python-version 3.12 \
  --python-platform aarch64-manylinux2014 \
  -r build/requirements.txt

cp -R src/ryanair_price_monitor "$package_dir/"
cp config/trips.json "$package_dir/config/"

(cd "$package_dir" && zip -qr -X ../../dist/lambda.zip . -x '*__pycache__*' '*.pyc')
echo "Built dist/lambda.zip ($(du -h dist/lambda.zip | cut -f1))"
