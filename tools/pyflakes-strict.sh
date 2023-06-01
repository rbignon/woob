#!/bin/sh -e

. "$(dirname $0)/common.sh"

cd "$(dirname $0)/.."

die () {
    echo "$@" >&2
    exit 1
}

$PYTHON -c 'import flake8' || die "Please install flake8 (e.g. apt install flake8)"
$PYTHON -c 'import flake8_import_order' || die "Please install flake8-import-order (e.g. pip3 install flake8-import-order)"
$PYTHON -c 'import bugbear' || die "Please install flake8-bugbear (e.g. pip3 install flake8-bugbear)"
$PYTHON -c 'import asttokens' || die "Please install asttokens (e.g. apt install python3-asttokens)"

err=0
echo "run flake8"
$PYTHON ./tools/hooks/run-flake8.py "$@" || err=1
echo "check if expression"
$PYTHON ./tools/hooks/check-ifexpr.py "$@" || err=1
echo "check string cut"
$PYTHON ./tools/hooks/check-stringcut.py "$@" || err=1
echo "check continuations"
$PYTHON ./tools/hooks/check-continuations.py "$@" || err=1
echo "check trailing commas"
$PYTHON ./tools/hooks/check-trailing-commas.py "$@" || err=1
echo "check line length"
$PYTHON ./tools/hooks/check-line-length.py -l 120 "$@" || err=1
echo "check op precedence"
$PYTHON ./tools/hooks/check-op-precedence.py "$@" || err=1
exit $err
