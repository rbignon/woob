#!/bin/sh -e

. "$(dirname $0)/common.sh"

cd "$(dirname $0)/.."

die () {
    echo "$@" >&2
    exit 1
}

# run with ECHO=O when calling the script to disable echo
ECHO=${ECHO:-1}

echomsg() {
    if [ "$ECHO" -eq 1 ]; then
        echo "$@"
    fi
}

$PYTHON -c 'import flake8' || die "Please install flake8 (e.g. apt install flake8)"
$PYTHON -c 'import flake8p' || die "Please install flake8-pyproject (e.g. pip3 install flake8-pyproject)"
$PYTHON -c 'import bugbear' || die "Please install flake8-bugbear (e.g. pip3 install flake8-bugbear)"
$PYTHON -c 'import asttokens' || die "Please install asttokens (e.g. apt install python3-asttokens)"

err=0
echomsg "run flake8"
$PYTHON ./tools/hooks/run-flake8.py "$@" || err=1
echomsg "check if expression"
$PYTHON ./tools/hooks/check-ifexpr.py "$@" || err=1
echomsg "check string cut"
$PYTHON ./tools/hooks/check-stringcut.py "$@" || err=1
echomsg "check continuations"
$PYTHON ./tools/hooks/check-continuations.py "$@" || err=1
echomsg "check trailing commas"
$PYTHON ./tools/hooks/check-trailing-commas.py "$@" || err=1
echomsg "check line length"
$PYTHON ./tools/hooks/check-line-length.py -l 120 "$@" || err=1
echomsg "check op precedence"
$PYTHON ./tools/hooks/check-op-precedence.py "$@" || err=1
exit $err
