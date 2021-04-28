Woob module cookiecutter template
=================================

This is a basic template for scaffolding woob modules with cookiecutter.

How to use
----------

Run cookiecutter:

    cookiecutter -o ../../modules .

It will ask a few questions:

    full_name [Your Name]:
    email [yourmail@example.com]:
    site_url [https://example.com]:
    site_name [Example]:
    capability [CapSomething]:
    module_name [twitter]:
    class_prefix [TwitterSimple]:
    year [2021]:

Develop by editing files in `../modules/your_module/*.py`.

Don't forget to let woob detect your module:

    woob update

Create an instance of your module:

    [my_backend]
    _module = my_module
    login = something
    password =

Then you can test your module with the appropriate command:

    woob something -d -b my_backend

Requirements
------------

This template requires at least cookiecutter 1.7.1.
