# -*- coding: utf-8 -*-

# Copyright(C) 2014 Romain Bignon
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from functools import wraps
import re
from urllib.parse import unquote

import requests

from woob.browser.filters.base import _Filter
from woob.tools.regex_helper import normalize

ABSOLUTE_URL_PATTERN_RE = re.compile(r'^[\w\?]+://[^/].*')


class UrlNotResolvable(Exception):
    """
    Raised when trying to locate on an URL instance which url pattern is not resolvable as a real url.
    """


class URL(object):
    """
    A description of an URL on the PagesBrowser website.

    It takes one or several regexps to match urls, and an optional Page
    class which is instancied by PagesBrowser.open if the page matches a regex.

    :param base: The name of the browser's property containing the base URL.
    """
    _creation_counter = 0

    def __init__(self, *args, base='BASEURL'):
        self.urls = []
        self.klass = None
        self.browser = None
        for arg in args:
            if isinstance(arg, str):
                self.urls.append(arg)
            if isinstance(arg, type):
                self.klass = arg

        self._base = base
        self._creation_counter = URL._creation_counter
        URL._creation_counter += 1

    def is_here(self, **kwargs):
        """
        Returns True if the current page of browser matches this URL.
        If arguments are provided, and only then, they are checked against the arguments
        that were used to build the current page URL.
        """
        assert self.klass is not None, "You can use this method only if there is a Page class handler."

        if len(kwargs):
            params = self.match(self.build(**kwargs)).groupdict()
        else:
            params = None

        # XXX use unquote on current params values because if there are spaces
        # or special characters in them, it is encoded only in but not in kwargs.
        return self.browser.page and isinstance(self.browser.page, self.klass) \
            and (params is None or params == dict([(k,unquote(v)) for k,v in self.browser.page.params.items()]))

    def stay_or_go(self, params=None, data=None, json=None, method=None, headers=None, **kwargs):
        """
        Request to go on this url only if we aren't already here.

        Arguments are optional parameters for url.

        >>> url = URL('http://exawple.org/(?P<pagename>).html')
        >>> url.stay_or_go(pagename='index')
        """
        if self.is_here(**kwargs):
            return self.browser.page

        return self.go(params=params, data=data, json=json, method=method, headers=headers, **kwargs)

    def go(self, *, params=None, data=None, json=None, method=None, headers=None, **kwargs):
        """
        Request to go on this url.

        Arguments are optional parameters for url.

        >>> url = URL('http://exawple.org/(?P<pagename>).html')
        >>> url.stay_or_go(pagename='index')
        """
        r = self.browser.location(self.build(**kwargs), params=params, data=data, json=json, method=method, headers=headers or {})
        return r.page or r

    def open(self, *, params=None, data=None, json=None, method=None, headers=None, is_async=False, callback=lambda response: response, **kwargs):
        """
        Request to open on this url.

        Arguments are optional parameters for url.

        :param data: POST data
        :type url: str or dict or None

        >>> url = URL('http://exawple.org/(?P<pagename>).html')
        >>> url.open(pagename='index')
        """
        r = self.browser.open(self.build(**kwargs), params=params, data=data, json=json, method=method, headers=headers or {}, is_async=is_async, callback=callback)

        if hasattr(r, 'page') and r.page:
            return r.page
        return r

    def get_base_url(self, browser=None, for_pattern=None):
        """Get the browser's base URL for the instance."""
        browser = browser or self.browser
        if browser is None:
            raise ValueError('URL browser is not set')

        value = getattr(browser, self._base, None)
        if not isinstance(value, str):
            msg = f'Browser {self._base} property is None or not defined'
            if for_pattern:
                msg += f', URL {for_pattern} should be defined as absolute'
            raise ValueError(msg)

        return value

    def build(self, **kwargs):
        """
        Build an url with the given arguments from URL's regexps.

        :param param: Query string parameters

        :rtype: :class:`str`
        :raises: :class:`UrlNotResolvable` if unable to resolve a correct url with the given arguments.
        """
        browser = kwargs.pop('browser', self.browser)
        params = kwargs.pop('params', None)
        patterns = []
        for url in self.urls:
            patterns += normalize(url)

        base = None
        for pattern, _ in patterns:
            url = pattern
            # only use full-name substitutions, to allow % in URLs
            args = kwargs.copy()
            for key in list(args.keys()):  # need to use keys() because of pop()
                search = '%%(%s)s' % key
                if search in pattern:
                    url = url.replace(search, str(args.pop(key)))
            # if there are named substitutions left, ignore pattern
            if re.search(r'%\([A-z_]+\)s', url):
                continue
            # if not all args were used
            if len(args):
                continue

            if base is None and not ABSOLUTE_URL_PATTERN_RE.match(url):
                base = self.get_base_url(browser=browser, for_pattern=url)
                url = browser.absurl(url, base=base)

            if params:
                p = requests.models.PreparedRequest()
                p.prepare_url(url, params)
                url = p.url
            return url

        raise UrlNotResolvable('Unable to resolve URL with %r. Available are %s' % (kwargs, ', '.join([pattern for pattern, _ in patterns])))

    def match(self, url, base=None):
        """
        Check if the given url match this object.
        """
        for regex in self.urls:
            if not ABSOLUTE_URL_PATTERN_RE.match(regex):
                if not base:
                    base = self.get_base_url(browser=None, for_pattern=regex)

                regex = re.escape(base).rstrip('/') + '/' + regex.lstrip('/')

            m = re.match(regex, url)
            if m:
                return m

    def handle(self, response):
        """
        Handle a HTTP response to get an instance of the klass if it matches.
        """
        if self.klass is None:
            return
        if response.request.method == 'HEAD':
            return

        m = self.match(response.url)
        if m:
            page = self.klass(self.browser, response, m.groupdict())
            if hasattr(page, 'is_here'):
                if page.is_here is None or page.is_here is True:
                    return page
                elif page.is_here is False:
                    return  # no page!
                elif isinstance(page.is_here, _Filter):
                    if page.is_here(page.doc):
                        return page
                elif callable(page.is_here):
                    if page.is_here():
                        return page
                else:
                    assert isinstance(page.is_here, str)
                    if page.doc.xpath(page.is_here):
                        return page
            else:
                return page

    def id2url(self, func):
        r"""
        Helper decorator to get an URL if the given first parameter is an ID.
        """

        @wraps(func)
        def inner(browser, id_or_url, *args, **kwargs):
            if re.match('^https?://.*', id_or_url):
                base = self.get_base_url(browser=browser)
                if not self.match(id_or_url, base=base):
                    return
            else:
                id_or_url = self.build(id=id_or_url, browser=browser)

            return func(browser, id_or_url, *args, **kwargs)
        return inner

    def with_page(self, cls):
        """Get a new URL with the same path but a different page class.

        :param cls: The new page class to use.
        """
        new_url = self.__class__(*self.urls, cls, base=self._base)
        new_url.browser = None
        return new_url

    def with_urls(self, *urls, clear=True, match_new_first=True):
        """Get a new URL object with the same page but with different paths.

        :param str urls: List of urls handled by the page
        :param bool clear: If True, the page will only handled the given urls.
                           Otherwise, the urls are added to already handled
                           urls.
        :param bool match_new_first: If true, new paths will be matched first
                                     for this URL; this parameter is ignored
                                     when `clear` is True.
        """
        if not clear:
            # needed to extend self.urls which is a list
            urls = list(urls)
            if match_new_first:
                urls = urls + self.urls
            else:
                urls = self.urls + urls

        # We only want unique patterns here.
        urls = list(dict.fromkeys(urls))

        new_url = self.__class__(*urls, self.klass, base=self._base)
        new_url.browser = None
        return new_url


class BrowserParamURL(URL):
    r"""A URL that automatically fills some params from browser attributes.

    URL patterns having groups named "browser_*" will pick the relevant
    attribute from the browser. For example:

        foo = BrowserParamURL(r'/foo\?bar=(?P<browser_token>\w+)')

    The browser is expected to have a `.token` attribute and it will be passed
    automatically when just calling `foo.go()`, it's equivalent to
    `foo.go(browser_token=browser.token)`.

    Warning: all `browser_*` params will be passed, having multiple patterns
    with different groups in a `BrowserParamURL` is risky.
    """

    def build(self, **kwargs):
        prefix = 'browser_'

        for arg in kwargs:
            if arg.startswith(prefix):
                raise ValueError('parameter %r is reserved by URL pattern')

        for url in self.urls:
            for groupname in re.compile(url).groupindex:
                if groupname.startswith(prefix):
                    attrname = groupname[len(prefix):]
                    kwargs[groupname] = getattr(self.browser, attrname)

        return super(BrowserParamURL, self).build(**kwargs)


def normalize_url(url):
    """Normalize URL by lower-casing the domain and other fixes.

    Lower-cases the domain, removes the default port and a trailing dot.

    >>> normalize_url('http://EXAMPLE:80')
    'http://example'
    """

    def norm_domain(m):
        # don't use urlparse/urlunparse because it might do too much normalization

        auth, authsep, hostport = m.group(2).rpartition('@')
        host, portsep, port = hostport.partition(':')

        if (
            (port == '443' and m.group(1) == 'https://')
            or (port == '80' and m.group(1) == 'http://')
        ):
            portsep = port = ''

        host = host.lower().rstrip('.')

        return ''.join((m.group(1), auth, authsep, host, portsep, port))

    return re.sub(r'^(https?://)([^/#?]+)', norm_domain, url)
