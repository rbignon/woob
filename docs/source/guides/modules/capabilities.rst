Select capabilities
===================

Each module implements one or many :doc:`capabilities </api/capabilities/index>` to tell what kind of features the
website provides. A capability is a class derived from :class:`woob.capabilities.base.Capability` and with some abstract
methods (which raise :py:exc:`NotImplementedError`).

A capability needs to be as generic as possible to allow a maximum number of modules to implement it.
Anyway, if you really need to handle website specificities, you can create more specific sub-capabilities.

For example, there is the :class:`~woob.capabilities.messages.CapMessages` capability, with the associated
:class:`~woob.capabilities.messages.CapMessagesPost` capability to allow answers to messages.

Pick an existing capability
---------------------------

When you want to create a new module, you may have a look at existing capabilities to decide which one can be
implemented. It is quite important, because each already existing capability is supported by at least one application.
So if your new module implements an existing capability, it will be usable from the existing applications right now.

Create a new capability
-----------------------

If the website you want to manage implements some extra-features which are not implemented by any capability,
you can introduce a new capability.

You should read the related guide to know :doc:`how to create a capability </guides/capabilities/create>`.
