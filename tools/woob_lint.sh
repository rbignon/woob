#!/bin/sh

# stop on failure
set -e

. "$(dirname $0)/common.sh"

[ -z "${TMPDIR}" ] && TMPDIR="/tmp"

# do not allow undefined variables anymore
set -u
WOOB_TMPDIR=$(mktemp -d "${TMPDIR}/woob_lint.XXXXXX")

# path to sources
WOOB_DIR=$(cd $(dirname $0)/.. && pwd -P)
touch "${WOOB_TMPDIR}/backends"
chmod 600 "${WOOB_TMPDIR}/backends"
echo "file://$WOOB_DIR/modules" > "${WOOB_TMPDIR}/sources.list"

export WOOB_WORKDIR="${WOOB_TMPDIR}"
export WOOB_DATADIR="${WOOB_TMPDIR}"
export PYTHONPATH="${WOOB_DIR}"
set +e
# TODO can we require woob to be installed before being able to run run_tests.sh?
# if we can, then woob config is present in PATH (virtualenv or whatever)
${PYTHON} -c "import sys; sys.argv='woob-config update'.split(); from woob.applications.config import AppConfig; AppConfig.run()"

$PYTHON "${WOOB_DIR}/tools/woob_lint.py"

# allow failing commands past this point
STATUS=$?

rm -rf "${WOOB_TMPDIR}"

exit $STATUS
