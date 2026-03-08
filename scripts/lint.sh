#!/usr/bin/env bash

err=0

if [[ "${1:-}" == "--check" ]]; then
  check_mode="--check --diff"
  fix_mode=""
else
  check_mode=""
  fix_mode="--fix"
fi

YELLOW='\033[33m'
RED='\033[0;31m'
NC='\033[0m'

run() {
  printf "${YELLOW}%s${NC}\n" "$1" >&2
  shift
  "$@" || { printf "${RED}fails${NC}\n" >&2; err=1; }
}

run "ruff check"  ruff check  src tests $fix_mode
run "ruff format" ruff format src tests $check_mode

exit $err
