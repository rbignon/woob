Setup your development environment
==================================

To develop on woob, you have to setup a development environment.

Git installation
----------------

Clone a git repository with this command::

    $ git clone https://gitlab.com/woob/woob.git

We don't want to install woob on the whole system, so we create local directories where
we will put symbolic links to sources::

    $ cd $HOME/src/woob

If not in a virtualenv, executables are in ``~/.local/bin`` and modules are in
``~/.local/lib/``:

    $ pip install --user -e .

If inside a virtualenv, no need to update the paths, they are all in the virtualenv.

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

For example, instead of running `woob video -b youtube search plop`, you would run::

    $ ./tools/local_run.sh video -b youtube search plop


Conclusion
----------

You can now edit sources, :doc:`create a module </guides/module>` or :doc:`an application </guides/application>`.
