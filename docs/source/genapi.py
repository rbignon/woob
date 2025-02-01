#!/usr/bin/env python3

import os


def genapi():
    os.system("rm -rf api")
    os.system("mkdir api")
    os.chdir("api")
    for root, dirs, files in os.walk("../../../woob/"):
        root = root.split("/", 4)[-1]
        if root.startswith("applications") or root.startswith("__") or root.endswith("__"):
            continue

        if root.strip():
            os.system("mkdir -p %s" % root)
            module = ".".join(["woob"] + root.split("/"))
        else:
            module = "woob"

        subs = set()
        for f in files:
            if "." not in f:
                continue

            f, ext = f.rsplit(".", 1)
            if ext != "py" or f.startswith("__"):
                continue

            subs.add(f)
            with open(os.path.join(root, "%s.rst" % f), "w") as fp:
                fmod = ".".join([module, f])
                fp.write(
                    f""":mod:`{fmod}`
======={'=' * len(fmod)}

.. automodule:: {fmod}
   :show-inheritance:
   :members:
   :undoc-members:"""
                )  # % {'module': fmod,
                #    'equals': '=' * len(fmod)})

        for d in dirs:
            if (not root and d == "applications") or d == "__pycache__":
                continue
            subs.add("%s/index" % d)

        if module == "woob":
            continue

        with open(os.path.join(root, "index.rst"), "w") as fp:
            m = ":mod:`%s`" % module
            subs = "\n   ".join(sorted(subs))
            fp.write(
                f"""{m}
{'=' * len(m)}

.. toctree::
   :maxdepth: 2

   {subs}
"""
            )


if __name__ == "__main__":
    genapi()
