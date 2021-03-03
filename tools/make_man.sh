#!/bin/sh

# stop on failure
set -e

. "$(dirname $0)/common.sh"

# Use C local to avoid local dates in headers
export LANG=en_US.utf8

# disable termcolor
export ANSI_COLORS_DISABLED=1

[ -z "${TMPDIR}" ] && TMPDIR="/tmp"

# do not allow undefined variables anymore
set -u
WOOB_TMPDIR=$(mktemp -d "${TMPDIR}/woob_man.XXXXXX")

# path to sources
WOOB_DIR=$(cd $(dirname $0)/.. && pwd -P)
touch "${WOOB_TMPDIR}/backends"
chmod 600 "${WOOB_TMPDIR}/backends"
echo "file://$WOOB_DIR/modules" > "${WOOB_TMPDIR}/sources.list"

export WOOB_WORKDIR="${WOOB_TMPDIR}"
export WOOB_DATADIR="${WOOB_TMPDIR}"
export PYTHONPATH="${WOOB_DIR}"
# TODO can we require woob to be installed before being able to run run_tests.sh?
# if we can, then woob config is present in PATH (virtualenv or whatever)
${PYTHON} -c "import sys; sys.argv='woob-config update'.split(); from woob.applications.config import AppConfig; AppConfig.run()"

$PYTHON "${WOOB_DIR}/tools/make_man.py"

# allow failing commands past this point
STATUS=$?

rm -rf "${WOOB_TMPDIR}"

exit $STATUS
