====
Woob
====

|version| |last-commit| |python| |license|

.. |version| image:: https://img.shields.io/pypi/v/woob
    :target: https://pypi.org/project/woob/
    :alt: Package Version
.. |last-commit| image:: https://img.shields.io/gitlab/last-commit/woob/woob
    :target: https://gitlab.com/woob/woob/
    :alt: Last commit
.. |python| image:: https://img.shields.io/pypi/pyversions/woob
    :target: https://pypi.org/project/woob/
    :alt: Python Version
.. |license| image:: https://img.shields.io/pypi/l/woob
    :target: https://gitlab.com/woob/woob/-/blob/master/COPYING.LESSER
    :alt: License

Woob (`Web Outside of Browsers`) is a library which provides a Python standardized API and data models to
access websites.

Overview
========

.. image:: https://woob.dev/_images/arch.png

There are three main concepts:

* `Capabilities <https://woob.dev/guides/capabilities>`_: This is a standardized interface
  to access a specific kind of website. It provides an unified API and standard
  datamodels;
* `Modules <https://woob.dev/guides/modules>`_: A module is dedicated to a specific
  website. It can implements several capabilities (for example `paypal <https://paypal.com>`_ module may
  implement ``CapBank`` to get bank
  informations, ``CapTransfer`` to
  initiate a transfer, ``CapProfile`` to get
  information about the customer, and ``CapDocument`` to get documents);
* `Backends <https://woob.dev/guides/user/quickstart>`_: You can load a module several times,
  with different configurations. For example, if you have two PayPal accounts,
  you can create two backends of the same module with different credentials.

The main ``Woob`` class let configure new backends and do aggregated calls to
every backends loaded with a specific capability.

For example, once backends are loaded, you can call ``iter_accounts()`` and
you'll get accounts in the same ``Account`` data model for all backends
implementing ``CapBank``:

.. code-block:: python

   >>> from woob.core import Woob
   >>> from woob.capabilities.bank import CapBank
   >>> w = Woob()
   >>> w.load_backends(CapBank)
   {'societegenerale': <Backend 'societegenerale'>,
    'creditmutuel': <Backend 'creditmutuel'>}
   >>> accounts = list(w.iter_accounts())
   >>> print(accounts)
   [<Account id='7418529638527412' label=u'Compte de ch\xe8ques'>,
    <Account id='9876543216549871' label=u'Livret A'>,
    <Account id='123456789123456789123EUR' label=u'C/C Eurocompte Confort M Roger Philibert'>]
   >>> accounts[0].balance
   Decimal('87.32')


Applications
============

If you are looking for applications using the woob library, visit `woob.tech <https://woob.tech>`_.


Installation
============

Read this `documentation <https://woob.dev/guides/install/>`_.

Documentation
=============

More information about how to use woob at `woob.dev <https://woob.dev>`_.

Contributing
============

If you want to contribute to woob (patch of the core, creating new modules,
etc.), `read this <https://woob.dev/guides/contribute/>`_.

Chat with us
============

* `#woob @ liberachat <ircs://irc.libera.chat/woob>`_
* `#woob @ matrix.org <https://matrix.to/#/#woob:matrix.org>`_
