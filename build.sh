#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

python -m pip install -r requirements/render.txt
python backend/manage.py collectstatic --noinput --settings=config.settings_production
