#!/bin/bash
#
# Try to load all modules. It may fails if there are missing dependences in the
# module requirements.txt

errors=''


for module in $(find modules/* -maxdepth 0 -type d -exec basename {} \;); do
  echo "-------"
  echo "Module $module"

  # Find a requirements.txt and install dependences. We exclude woob to avoid
  # installing it from PyPI.
  module_requirements=modules/$module/requirements.txt
  tmp_requirements=$(mktemp)
  [ -f "$module_requirements" ] && cat "$module_requirements" | grep -v woob > "$tmp_requirements"
  [ -s "$tmp_requirements" ] && pip install -r "$tmp_requirements"

  # Python script to load module
  output=$(python -c "
from woob.core import WoobBase
w = WoobBase('modules')

try:
    w.load_or_install_module('$module')
except Exception as e:
    print(e)
")

  # Uninstall module dependences
  [ -s "$tmp_requirements" ] && pip uninstall -y -r "$tmp_requirements"

  # The python script write something on stdout only if there is an error.
  if [ -n "$output" ]; then
    echo "Error: $output"
    errors="$errors$module: $output"$'\n'
  else
    echo "OK"
  fi
done

echo "-------"

if [ -n "$errors" ]; then
  echo "Errors to load modules:"
  echo "$errors"
  exit 1
fi
