if [ -z "${PYTHON-}" ]; then
    which python3.9 >/dev/null 2>&1 && PYTHON=$(which python3.9)
    which python3.10 >/dev/null 2>&1 && PYTHON=$(which python3.10)
    which python3.11 >/dev/null 2>&1 && PYTHON=$(which python3.11)
    which python3.12 >/dev/null 2>&1 && PYTHON=$(which python3.12)
    which python3.13 >/dev/null 2>&1 && PYTHON=$(which python3.13)
    which python3 >/dev/null 2>&1 && PYTHON=$(which python3)
fi
