#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

if [ ! -f .env ]; then
    printf '%s\n' 'Create .env from .env.example and set the required secrets before starting.' >&2
    exit 1
fi

if [ ! -f frontend/package-lock.json ]; then
    docker compose --profile tools run --rm frontend-lock
fi

docker compose up --build -d