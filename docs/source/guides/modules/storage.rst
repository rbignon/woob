Storage
=======

The application can provide a storage to let your backend store data. So, you can define the structure of your storage space::

    STORAGE = {'seen': {}}

To store and read data in your storage space, use the ``storage`` attribute of your :class:`~woob.tools.backend.Module`
object.

It implements the methods of :class:`~woob.tools.backend.BackendStorage`.
