Pages
=====

Pages classes
-------------

For each page you want to handle, you have to create an associated class derived from one of these classes:

* :class:`~woob.browser.pages.HTMLPage` - a HTML page
* :class:`~woob.browser.pages.XMLPage` - a XML document
* :class:`~woob.browser.pages.JsonPage` - a Json object
* :class:`~woob.browser.pages.CsvPage` - a CSV table

In the file ``pages.py``, you can write, for example::

    from woob.browser.pages import HTMLPage

    __all__ = ['IndexPage', 'ListPage']

    class IndexPage(HTMLPage):
        pass

    class ListPage(HTMLPage):
        def iter_accounts():
            return iter([])

``IndexPage`` is the class we will use to get information from the home page of the website, and ``ListPage`` will handle pages
which list accounts.

Then, you have to declare them in your browser, with the :class:`~woob.browser.url.URL` object::

    from woob.browser import PagesBrowser, URL
    from .pages import IndexPage, ListPage

    # ...
    class ExampleBrowser(PagesBrowser):
        # ...

        home = URL('/$', IndexPage)
        accounts = URL('/accounts$', ListPage)

Easy, isn't it? The first parameters are regexps of the urls (if you give only a path, it uses the ``BASEURL`` class attribute), and the last one is the class used to handle the response.

.. note::

    You can handle parameters in the URL using ``(?P<someName>)``. You can then use a keyword argument `someName` to
    bind a value to this parameter in :func:`~woob.browser.url.URL.stay_or_go`.

Each time you will go on the home page, ``IndexPage`` will be instanced and set as the ``page`` attribute.

For example, we can now implement some methods in ``ExampleBrowser``::

    from woob.browser import PagesBrowser

    class ExampleBrowser(PagesBrowser):
        # ...
        def go_home(self):
            self.home.go()

            assert self.home.is_here()

        def iter_accounts_list(self):
            self.accounts.stay_or_go()

            return self.page.iter_accounts()

When calling the :func:`~woob.browser.url.URL.go` method, it reads the first regexp url of our :class:`~woob.browser.url.URL` object, and go on the page.

:func:`~woob.browser.url.URL.stay_or_go` is used when you want to relocate on the page only if we aren't already on it.

Once we are on the ``ListPage``, we can call every methods of the ``page`` object.

Use it in the module
--------------------

Now you have a functional browser, you can use it in your class ``ExampleModule`` by defining it with the ``BROWSER`` attribute::

    from woob.tools.backend import Module
    from woob.capabilities.bank import CapBank

    from .browser import ExampleBrowser

    # ...
    class ExampleModule(Module, CapBank):
        # ...
        BROWSER = ExampleBrowser

You can now access it with member ``browser``. The class is instanced at the first call to this attribute.

For example, we can now implement :func:`CapBank.iter_accounts <woob.capabilities.bank.base.CapBank.iter_accounts>`::

    def iter_accounts(self):
        return self.browser.iter_accounts_list()

For this method, we only call immediately ``ExampleBrowser.iter_accounts_list``, as there isn't anything else to do around.


Parsing of pages
----------------

.. note::
    Depending of the base class you use for your page, it will parse html, json, csv, etc. In this section, we will
    describe the case of HTML documents.


When your browser locates on a page, an instance of the class related to the
:class:`~woob.browser.url.URL` attribute which matches the url
is created. You can declare methods on your class to allow your browser to
interact with it.

The first thing to know is that page parsing is done in a descriptive way. You
don't have to loop on HTML elements to construct the object. Just describe how
to get correct data to construct it. It is the ``Browser`` class work to actually
construct the object.

For example::

    from woob.browser.pages import LoggedPage, HTMLPage
    from woob.browser.filters.html import Attr
    from woob.browser.filters.standard import CleanDecimal, CleanText
    from woob.capabilities.bank import Account
    from woob.browser.elements import method, ListElement, ItemElement

    class ListPage(LoggedPage, HTMLPage):
        @method
        class get_accounts(ListElement):
            item_xpath = '//ul[@id="list"]/li'

            class item(ItemElement):
                klass = Account

                obj_id = Attr('id')
                obj_label = CleanText('./td[@class="name"]')
                obj_balance = CleanDecimal('./td[@class="balance"]')

As you can see, we first set ``item_xpath`` which is the xpath string used to iterate over elements to access data. In a
second time we define ``klass`` which is the real class of our object. And then we describe how to fill each object's
attribute using what we call filters. To set an attribute `foobar` of the object, we should fill `obj_foobar`. It can
either be a filter, a constant or a function.

Some example of filters:

* :class:`~woob.browser.filters.html.Attr`: extract a tag attribute
* :class:`~woob.browser.filters.standard.CleanText`: get a cleaned text from an element
* :class:`~woob.browser.filters.standard.CleanDecimal`: get a cleaned Decimal value from an element
* :class:`~woob.browser.filters.standard.Date`: read common date formats
* :class:`~woob.browser.filters.standard.DateTime`: read common datetime formats
* :class:`~woob.browser.filters.standard.Env`: typically useful to get a named parameter in the URL (passed as a
  keyword argument to :func:`~woob.browser.url.URL.stay_or_go`)
* :class:`~woob.browser.filters.standard.Eval`: evaluate a lambda on the given value
* :class:`~woob.browser.filters.standard.Format`: a formatting filter, uses the standard Python format string
  notations.
* :class:`~woob.browser.filters.html.Link`: get the link uri of an element
* :class:`~woob.browser.filters.standard.Regexp`: apply a regex
* :class:`~woob.browser.filters.standard.Time`: read common time formats
* :class:`~woob.browser.filters.standard.Type`: get a cleaned value of any type from an element text

The full list of filters can be found in :doc:`woob.browser.filters </api/browser/filters/index>`.

Filters can be combined. For example::

    obj_id = Link('./a[1]') & Regexp(r'id=(\d+)') & Type(type=int)

This code do several things, in order:

#) extract the href attribute of our item first ``a`` tag child
#) apply a regex to extract a value
#) convert this value to int type


When you want to access some attributes of your :class:`~woob.browser.pages.HTMLPage` object to fill an
attribute in a Filter, you should use the function construction for this attribute. For example::

    def obj_url(self):
        return (
            u'%s%s' % (
                self.page.browser.BASEURL,
                Link(
                    u'//a[1]'
                )(self)
            )
    )

which will return a full URL, concatenating the ``BASEURL`` from the browser
with the (relative) link uri of the first ``a`` tag child.

.. note::

   All objects ID must be unique, and useful to get more information later

Your module is now functional and you can use this command::

    $ woob bank -b example list

.. note::

    You can pass ``-a`` command-line argument to any woob application to log
    all the possible debug output (including requests and their parameters, raw
    responses and loaded HTML pages) in a temporary directory, indicated at the
    launch of the program.
