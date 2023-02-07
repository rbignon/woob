Browsers
========

.. image:: browsers.png

Most of modules use a class derived from :class:`~woob.browser.browsers.PagesBrowser` or
:class:`~woob.browser.browsers.LoginBrowser` (for authenticated websites) to interact with a website or
:class:`~woob.browser.browsers.APIBrowser` to interact with an API.

Edit ``browser.py``::

    # -*- coding: utf-8 -*-

    from woob.browser import PagesBrowser

    __all__ = ['ExampleBrowser']

    class ExampleBrowser(PagesBrowser):
        BASEURL = 'https://www.example.com'

There are several possible class attributes:

* **BASEURL** - base url of website used for absolute paths given to :class:`~woob.browser.browsers.PagesBrowser.open` or :class:`~woob.browser.browsers.PagesBrowser.location`
* **PROFILE** - defines the behavior of your browser against the website. By default this is Firefox, but you can import other profiles
* **TIMEOUT** - defines the timeout for requests (defaults to 10 seconds)
* **VERIFY** - SSL verification (if the protocol used is **https**)

Documentation:

.. toctree::
   :maxdepth: 1

   browsers
   pages
   login
   cookbook
