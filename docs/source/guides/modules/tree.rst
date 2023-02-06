The module tree
***************

Create a new directory in ``modules/`` with the name of your module. In this example, we assume that we want to create a
module for a bank website which URL is http://www.example.com. So we will call our module ``example``, and the selected
capability is :class:`~woob.capabilities.bank.CapBank`.

It is recommended to use the helper tool ``tools/boilerplate.py`` to build your
module tree. There are several templates available:

* ``base`` - create only base files
* ``cap`` - create a module for a given capability

For example, use this command::

    $ tools/boilerplate.py cap example CapBank

In a module directory, there are commonly these files:

* ``__init__.py`` - needed in every python modules, it exports your :class:`~woob.tools.backend.Module` class.
* ``module.py`` - defines the main class of your module, which derives :class:`~woob.tools.backend.Module`.
* ``browser.py`` - your browser, derived from :class:`~woob.browser.browsers.Browser`, is called by your module to interact with the supported website.
* ``pages.py`` - all website's pages handled by the browser are defined here
* ``test.py`` - functional tests
* ``favicon.png`` - a 64x64 transparent PNG icon

.. note::

    A module can implement multiple capabilities, even though the ``tools/boilerplate.py`` script can only generate a
    template for a single capability. You can freely add inheritance from other capabilities afterwards in
    ``module.py``.

Update modules list
-------------------

As you are in development mode, to see your new module in ``woob config``'s list, you have to update ``modules/modules.list`` with this command::

    $ woob config update

To be sure your module is correctly added, use this command::

    $ woob config info example
    .------------------------------------------------------------------------------.
    | Module example                                                               |
    +-----------------.------------------------------------------------------------'
    | Version         | 201405191420
    | Maintainer      | John Smith <john.smith@example.com>
    | License         | LGPLv3+
    | Description     | Example bank website
    | Capabilities    | CapBank, CapCollection
    | Installed       | yes
    | Location        | /home/me/src/woob/modules/example
    '-----------------'

If the last command does not work, check your :doc:`repositories setup
</guides/install/index>`. In particular, when you want to edit an already existing
module, you should take great care of setting your development environment
correctly, or your changes to the module will not have any effect. You can also
use ``./tools/local_run.sh`` script as a quick and dirty method of forcing
woob applications to use local modules rather than remote ones.
