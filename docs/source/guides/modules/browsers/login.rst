Login management
----------------

When the website requires to be authenticated, you have to give credentials to the constructor of the browser. You can redefine
the method :func:`~woob.tools.backend.Module.create_default_browser`::

    from woob.tools.backend import Module
    from woob.capabilities.bank import CapBank

    class ExampleModule(Module, CapBank):
        # ...
        def create_default_browser(self):
            return self.create_browser(self.config['username'].get(), self.config['password'].get())

On the browser side, you need to inherit from :func:`~woob.browser.browsers.LoginBrowser` and to implement the function
:func:`~woob.browser.browsers.LoginBrowser.do_login`::

    from woob.browser import LoginBrowser
    from woob.exceptions import BrowserIncorrectPassword

    class ExampleBrowser(LoginBrowser):
        login = URL('/login', LoginPage)
        # ...

        def do_login(self):
            self.login.stay_or_go()

            self.page.login(self.username, self.password)

            if self.login_error.is_here():
                raise BrowserIncorrectPassword(self.page.get_error())

You may provide a custom :func:`~woob.browser.browsers.LoginBrowser.do_logout` function if you need to customize the default logout process, which simply clears all cookies.

Also, your ``LoginPage`` may look like::

    from woob.browser.pages import HTMLPage

    class LoginPage(HTMLPage):
        def login(self, username, password):
            form = self.get_form(name='auth')
            form['username'] = username
            form['password'] = password
            form.submit()

Then, each method on your browser which needs your user to be authenticated may be decorated by :func:`~woob.browser.browsers.need_login`::

    from woob.browser import LoginBrowser, URL
    from woob.browser import need_login

    class ExampleBrowser(LoginBrowser):
        accounts = URL('/accounts$', ListPage)

        @need_login
        def iter_accounts(self):
            self.accounts.stay_or_go()
            return self.page.get_accounts()

You finally have to set correctly the :func:`~woob.browser.pages.Page.logged` attribute of each page you use.  The :func:`~woob.browser.browsers.need_login`
decorator checks if the current page is a logged one by reading the attribute :func:`~woob.browser.pages.Page.logged` of the instance. This attributes
defaults to  ``False``, which means that :func:`~woob.browser.browsers.need_login` will first call
:func:`~woob.browser.browsers.LoginBrowser.do_login` before calling the decorated method.

You can either define it yourself, as a class boolean attribute or as a property, or inherit your class from :class:`~woob.browser.pages.LoggedPage`.
In the latter case, remember that Python inheritance requires the :class:`~woob.browser.pages.LoggedPage` to be placed first such as in::

    from woob.browser.pages import LoggedPage, HTMLPage

    class OnlyForLoggedUserPage(LoggedPage, HTMLPage):
        # ...
