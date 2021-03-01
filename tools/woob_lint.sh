#!/bin/sh

# stop on failure
set -e

. "$(dirname $0)/common.sh"

[ -z "${TMPDIR}" ] && TMPDIR="/tmp"

# do not allow undefined variables anymore
set -u
WEBOOB_TMPDIR=$(mktemp -d "${TMPDIR}/woob_lint.XXXXXX")

# path to sources
WEBOOB_DIR=$(cd $(dirname $0)/.. && pwd -P)
touch "${WEBOOB_TMPDIR}/backends"
chmod 600 "${WEBOOB_TMPDIR}/backends"
echo "file://$WEBOOB_DIR/modules" > "${WEBOOB_TMPDIR}/sources.list"

export WEBOOB_WORKDIR="${WEBOOB_TMPDIR}"
export WEBOOB_DATADIR="${WEBOOB_TMPDIR}"
export PYTHONPATH="${WEBOOB_DIR}"
set +e
# TODO can we require woob to be installed before being able to run run_tests.sh?
# if we can, then woob config is present in PATH (virtualenv or whatever)
${PYTHON} -c "import sys; sys.argv='woob config update'.split(); from weboob.applications.config import AppConfig; AppConfig.run()"

$PYTHON "${WEBOOB_DIR}/tools/woob_lint.py"

# allow failing commands past this point
STATUS=$?

rm -rf "${WEBOOB_TMPDIR}"

exit $STATUS
