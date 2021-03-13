#!/usr/bin/env bash

# Mai available environment variables
#   * RSYNC_TARGET: target on which to rsync the xunit output.
#   * XUNIT_OUT: file in which xunit output should be saved.
#   * WOOB_BACKENDS: path to the Woob backends file to use.
#   * WOOB_CI_TARGET: URL of your Woob-CI instance.
#   * WOOB_CI_ORIGIN: origin for the Woob-CI data.

# stop on failure
set -e

. "$(dirname $0)/common.sh"

if [ -z "${PYTHON}" ]; then
    echo "Python required"
    exit 1
fi

if ! $PYTHON -c "import nose" 2>/dev/null; then
    echo "python-nose required"
    exit 1
fi

TEST_CORE=1
TEST_MODULES=1

for i in "$@"
do
case $i in
    --no-modules)
        TEST_MODULES=0
        shift
        ;;
    --no-core)
        TEST_CORE=0
        shift
        ;;
    *)
    ;;
esac
done

# path to sources
WOOB_DIR=$(cd $(dirname $0)/.. && pwd -P)

BACKEND="${1}"
if [ -z "${WOOB_WORKDIR}" ]; then
    # use the old workdir by default
    WOOB_WORKDIR="${HOME}/.woob"
    # but if we can find a valid xdg workdir, switch to it
    [ "${XDG_CONFIG_HOME}" != "" ] || XDG_CONFIG_HOME="${HOME}/.config"
    [ -d "${XDG_CONFIG_HOME}/woob" ] && WOOB_WORKDIR="${XDG_CONFIG_HOME}/woob"
fi
[ -z "${TMPDIR}" ] && TMPDIR="/tmp"
WOOB_TMPDIR=$(mktemp -d "${TMPDIR}/woob_test.XXXXXX")
[ -z "${WOOB_BACKENDS}" ] && WOOB_BACKENDS="${WOOB_WORKDIR}/backends"
[ -z "${WOOB_MODULES}" ] && WOOB_MODULES="${WOOB_DIR}/modules"
[ -z "${PYTHONPATH}" ] && PYTHONPATH=""

# allow private environment setup
[ -f "${WOOB_WORKDIR}/pre-test.sh" ] && source "${WOOB_WORKDIR}/pre-test.sh"

# setup xunit reporting (buildbot slaves only)
if [ -n "${RSYNC_TARGET}" ]; then
    # by default, builder name is containing directory name
    [ -z "${BUILDER_NAME}" ] && BUILDER_NAME=$(basename $(readlink -e $(dirname $0)/../..))
    XUNIT_OUT="${WOOB_TMPDIR}/xunit.xml"
else
    RSYNC_TARGET=""
fi

# Avoid undefined variables
if [ ! -n "${XUNIT_OUT}" ]; then
    XUNIT_OUT=""
fi

# Handle Woob-CI variables
if [ -n "${WOOB_CI_TARGET}" ]; then
    if [ ! -n "${WOOB_CI_ORIGIN}" ]; then
        WOOB_CI_ORIGIN="Woob unittests run"
    fi
    # Set up xunit reporting
    XUNIT_OUT="${WOOB_TMPDIR}/xunit.xml"
else
    WOOB_CI_TARGET=""
fi

# do not allow undefined variables anymore
set -u
if [ -f "${WOOB_BACKENDS}" ]; then
    cp "${WOOB_BACKENDS}" "${WOOB_TMPDIR}/backends"
else
    touch "${WOOB_TMPDIR}/backends"
    chmod go-r "${WOOB_TMPDIR}/backends"
fi

# xunit nose setup
if [ -n "${XUNIT_OUT}" ]; then
    XUNIT_ARGS="--with-xunit --xunit-file=${XUNIT_OUT}"
else
    XUNIT_ARGS=""
fi

[ $VER -eq 2 ] && $PYTHON "$(dirname $0)/stale_pyc.py"

echo "file://${WOOB_MODULES}" > "${WOOB_TMPDIR}/sources.list"

export WOOB_WORKDIR="${WOOB_TMPDIR}"
export WOOB_DATADIR="${WOOB_TMPDIR}"
export PYTHONPATH="${WOOB_DIR}:${PYTHONPATH}"
export NOSE_NOPATH="1"

if [[ ($TEST_MODULES = 1) || (-n "${BACKEND}") ]]; then
    # TODO can we require woob to be installed before being able to run run_tests.sh?
    # if we can, then woob config is present in PATH (virtualenv or whatever)
    ${PYTHON} -c "import sys; sys.argv='woob-config update'.split(); from woob.applications.config import AppConfig; AppConfig.run()"
fi

# allow failing commands past this point
set +e
set -o pipefail
STATUS_CORE=0
STATUS=0
if [ -n "${BACKEND}" ]; then
    ${PYTHON} -m nose -c /dev/null --logging-level=DEBUG -sv "${WOOB_MODULES}/${BACKEND}/test.py" ${XUNIT_ARGS}
    STATUS=$?
else
    if [ $TEST_CORE = 1 ]; then
        echo "=== Woob ==="
        CORE_TESTS=$(mktemp)
        ${PYTHON} -m nose --cover-package woob -c ${WOOB_DIR}/setup.cfg --logging-level=DEBUG -sv 2>&1 | tee "${CORE_TESTS}"
        STATUS_CORE=$?
        CORE_STMTS=$(grep "TOTAL" ${CORE_TESTS} | awk '{ print $2; }')
        CORE_MISS=$(grep "TOTAL" ${CORE_TESTS} | awk '{ print $3; }')
        CORE_COVERAGE=$(grep "TOTAL" ${CORE_TESTS} | awk '{ print $4; }')
        rm ${CORE_TESTS}
    fi

    if [ $TEST_MODULES = 1 ]; then
        echo "=== Modules ==="
        MODULES_TESTS=$(mktemp)
        MODULES_TO_TEST=$(find "${WOOB_MODULES}" -name "test.py" | sort | xargs echo)
        ${PYTHON} -m nose --with-coverage --cover-package modules -c /dev/null --logging-level=DEBUG -sv ${XUNIT_ARGS} ${MODULES_TO_TEST} 2>&1 | tee ${MODULES_TESTS}
        STATUS=$?
        MODULES_STMTS=$(grep "TOTAL" ${MODULES_TESTS} | awk '{ print $2; }')
        MODULES_MISS=$(grep "TOTAL" ${MODULES_TESTS} | awk '{ print $3; }')
        MODULES_COVERAGE=$(grep "TOTAL" ${MODULES_TESTS} | awk '{ print $4; }')
        rm ${MODULES_TESTS}
    fi

    # Compute total coverage
    echo "=== Total coverage ==="
    if [ $TEST_CORE = 1 ]; then
        echo "CORE COVERAGE: ${CORE_COVERAGE}"
    fi
    if [ $TEST_MODULES = 1 ]; then
        echo "MODULES COVERAGE: ${MODULES_COVERAGE}"
    fi

    if [[ ($TEST_CORE = 1) && ($TEST_MODULES = 1) ]]; then
        TOTAL_STMTS=$((${CORE_STMTS} + ${MODULES_STMTS}))
        TOTAL_MISS=$((${CORE_MISS} + ${MODULES_MISS}))
        TOTAL_COVERAGE=$((100 * (${TOTAL_STMTS} - ${TOTAL_MISS}) / ${TOTAL_STMTS}))
        echo "TOTAL: ${TOTAL_COVERAGE}%"
    fi
fi

# Rsync xunit transfer
if [ -n "${RSYNC_TARGET}" ]; then
    rsync -iz "${XUNIT_OUT}" "${RSYNC_TARGET}/${BUILDER_NAME}-$(date +%s).xml"
    rm "${XUNIT_OUT}"
fi

# Woob-CI upload
if [ -n "${WOOB_CI_TARGET}" ]; then
    JSON_MODULE_MATRIX=$(${PYTHON} "${WOOB_DIR}/tools/modules_testing_grid.py" "${XUNIT_OUT}" "${WOOB_CI_ORIGIN}")
    curl -H "Content-Type: application/json" --data "${JSON_MODULE_MATRIX}" "${WOOB_CI_TARGET}/api/v1/modules"
    rm "${XUNIT_OUT}"
fi

# safe removal
if [[ ($TEST_MODULES = 1) || (-n "${BACKEND}") ]]; then
    rm -r "${WOOB_TMPDIR}/icons" "${WOOB_TMPDIR}/repositories" "${WOOB_TMPDIR}/modules" "${WOOB_TMPDIR}/keyrings"
fi
rm "${WOOB_TMPDIR}/backends" "${WOOB_TMPDIR}/sources.list"
rmdir "${WOOB_TMPDIR}"

[ $STATUS_CORE -gt 0 ] && exit $STATUS_CORE
exit $STATUS
