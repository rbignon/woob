============
Installation
============

From PyPI
=========

You can use ``pip`` to install the latest `woob package <https://pypi.org/project/woob>`_::

    $ pip install woob


From source code
================

Clone the `git repository <https://gitlab.com/woob/woob>`_ with this command::

    $ git clone https://gitlab.com/woob/woob.git

Then, install with::

    $ cd woob
    $ pip install .


.. _dev-install:

Development environment
=======================

To develop on woob, you have to setup a development environment.

If not in a virtualenv, executables are in ``~/.local/bin`` and modules are in
``~/.local/lib/``::

    $ pip install --user -e .

If inside a virtualenv, no need to update the paths, they are all in the virtualenv::

    $ export PATH=$PATH:$HOME/.local/bin
    $ pip install -e .


Repositories setup
------------------

As you may know, woob installs modules from `remote repositories <http://woob.tech/modules>`_. As you
probably want to use modules in sources instead of stable ones, because you will change them, or create
a new one, you have to add this line at end of ``~/.config/woob/sources.list``::

    file:///home/me/src/woob/modules

Then, run this command::

    $ woob update

Run woob without installation
-------------------------------

This does not actually install anything, but lets you run woob from the source code,
while also using the modules from that source::

    $ ./tools/local_run.sh COMMAND [args ..]

For example, instead of running ``woob video -b youtube search plop``, you would run::

    $ ./tools/local_run.sh video -b youtube search plop
