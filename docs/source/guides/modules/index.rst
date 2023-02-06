Write a module
==============

This guide aims to learn how to write a new module for `woob <http://woob.tech>`_.

Before read it, you should :ref:`setup your development environment <dev-install>`.

A module is an interface between a website and woob. It represents the python code which is stored
in repositories.

woob applications need *backends* to interact with websites. A *backend* is an instance of a *module*, usually
with several parameters like your username, password, or other options. You can create multiple *backends*
for a single *module*.


.. toctree::
   :maxdepth: 1

   capabilities
   tree
   module
   browsers/index
   fillobj
   storage
   tests
