Module Tests
============

Every modules must have a tests suite to detect when there are changes on websites, or when a commit
breaks the behavior of the module.

Edit ``test.py`` and write, for example::

    # -*- coding: utf-8 -*-
    from woob.tools.test import BackendTest

    __all__ = ['ExampleTest']

    class ExampleTest(BackendTest):
        MODULE = 'example'

        def test_iter_accounts(self):
            accounts = list(self.backend.iter_accounts())

            self.assertTrue(len(accounts) > 0)

To try running test of your module, launch::

    $ tools/run_tests.sh example

For more information, look at the :ref:`contribute-tests` guides.
