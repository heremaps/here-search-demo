#!/usr/bin/env bash

declare -i err=0
if [ "${1:-}" = '--check' ]; then
  ruff_check_cmd='ruff check'
  mode='--check --diff'
else
  ruff_check_cmd='ruff check --fix'
  mode=
fi

declare -i line_length=120

YELLOW='\033[33m'
RED='\033[0;31m'
NC='\033[0m'

printf "${YELLOW}lint with mode=$mode${NC}\n" >&2

printf "${YELLOW}ruff check${NC}\n" >&2
$ruff_check_cmd --line-length $line_length src tests
_err=$?
err+=$_err
[[ $_err -ne 0 ]] && printf "${RED}fails${NC}\n" >&2

printf "${YELLOW}ruff format${NC}\n" >&2
ruff format $mode --line-length $line_length src tests
_err=$?
err+=$_err
[[ $_err -ne 0 ]] && printf "${RED}fails${NC}\n" >&2

printf "${YELLOW}isort${NC}\n" >&2
isort -m 3 --tc --atomic --line-length=$line_length --multi-line=3 $mode src
_err=$?
err+=$_err
[[ $_err -ne 0 ]] && printf "${RED}fails${NC}\n" >&2

exit $err
