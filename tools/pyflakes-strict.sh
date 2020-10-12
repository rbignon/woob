#!/bin/sh -e

. "$(dirname $0)/common.sh"

cd "$(dirname $0)/.."

die () {
    echo "$@" >&2
    exit 1
}

$PYTHON3 -c 'import flake8' || die "Please install flake8 (e.g. apt install flake8)"
$PYTHON3 -c 'import flake8_import_order' || die "Please install flake8-import-order (e.g. pip3 install flake8-import-order)"
$PYTHON3 -c 'import bugbear' || die "Please install flake8-bugbear (e.g. pip3 install flake8-bugbear)"
$PYTHON3 -c 'import asttokens' || die "Please install asttokens (e.g. apt install python3-asttokens)"

err=0
$PYTHON3 ./tools/hooks/run-flake8.py "$@"  || err=1
$PYTHON3 ./tools/hooks/check-ifexpr.py "$@" || err=1
$PYTHON3 ./tools/hooks/check-stringcut.py "$@" || err=1
$PYTHON3 ./tools/hooks/check-continuations.py "$@" || err=1
$PYTHON3 ./tools/hooks/check-trailing-commas.py "$@" || err=1
$PYTHON3 ./tools/hooks/check-line-length.py -l 120 "$@" || err=1
$PYTHON3 ./tools/hooks/check-op-precedence.py "$@" || err=1
exit $err
