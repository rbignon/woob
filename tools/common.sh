if [ -z "${PYTHON-}" ]; then
    which python3.5 >/dev/null 2>&1 && PYTHON=$(which python3.5)
    which python3.6 >/dev/null 2>&1 && PYTHON=$(which python3.6)
    which python3.7 >/dev/null 2>&1 && PYTHON=$(which python3.7)
    which python3.8 >/dev/null 2>&1 && PYTHON=$(which python3.8)
    which python3 >/dev/null 2>&1 && PYTHON=$(which python3)
fi
