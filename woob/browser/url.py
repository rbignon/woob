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

from __future__ import annotations

from functools import wraps
import re
from typing import Callable, Dict, Optional, TYPE_CHECKING, Tuple, Type, TypeVar
from urllib.parse import unquote

import requests

from woob.browser.pages import Page
from woob.browser.filters.base import _Filter
from woob.tools.regex_helper import normalize

if TYPE_CHECKING:
    from woob.browser.browsers import Browser

ABSOLUTE_URL_PATTERN_RE = re.compile(r'^[\w\?]+://[^/].*')

URLType = TypeVar('URLType', bound='URL')


class UrlNotResolvable(Exception):
    """
    Raised when trying to locate on an URL instance which url pattern is not resolvable as a real url.
    """


class URL:
    """
    A description of an URL on the PagesBrowser website.

    It takes one or several regexps to match urls, and an optional Page
    class which is instancied by PagesBrowser.open if the page matches a regex.

    .. warning::

        The ``methods`` parameter is only used for page matching, not request
        building using :py:meth:`URL.go` or :py:meth:`URL.open`; you must
        still set the method using these.

    :param base: The name of the browser's property containing the base URL.
    :param headers: Headers to include on requests using this URL.
    :param timeout: Timeout to use for this URL in particular.
    :param methods: Request HTTP methods to match the response.
    :param content_type: MIME type of the content to match the response with.
    """
    _creation_counter = 0

    def __init__(
        self, *args,
        base: str = 'BASEURL',
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        methods: Tuple[str, ...] = (),
        content_type: Optional[str] = None,
    ):
        if content_type is not None and ';' in content_type:
            raise ValueError(
                'Content-Type matching is only based on the MIME type, '
                + 'not additional properties such as encoding or version',
            )

        self.urls = []
        self.klass = None
        self.browser = None
        for arg in args:
            if isinstance(arg, str):
                self.urls.append(arg)
            if isinstance(arg, type):
                self.klass = arg

        self._base = base
        self._headers = headers
        self._timeout = timeout
        self._methods = tuple(methods)
        self._content_type = content_type
        self._creation_counter = URL._creation_counter
        URL._creation_counter += 1

    def is_here(self, **kwargs) -> bool:
        """
        Returns True if the current page of browser matches this URL.
        If arguments are provided, and only then, they are checked against the arguments
        that were used to build the current page URL.
        """
        assert self.klass is not None, "You can use this method only if there is a Page class handler."
        assert self.browser is not None

        if self.browser.page is None:
            return False

        if len(kwargs):
            m = self.match(self.build(**kwargs))
            assert m is not None
            params = m.groupdict()
        else:
            params = None

        if not isinstance(self.browser.page, self.klass):
            return False

        if self._methods:
            method = self.browser.response.request.method
            if method not in self._methods:
                return False

        if self._content_type is not None:
            content_type = self.browser.response.headers.get('Content-Type')
            if content_type is None:
                return False

            content_type, _, _ = content_type.partition(';')
            content_type = content_type.strip()
            if content_type != self._content_type:
                return False

        # XXX use unquote on current params values because if there are spaces
        # or special characters in them, it is encoded only in but not in kwargs.
        return (
            params is None or
            params == {k: unquote(v) for k, v in self.browser.page.params.items()}
        )

    def stay_or_go(
        self,
        params: Dict | None = None,
        data: str | Dict | None = None,
        json: Dict | None = None,
        method: str | None = None,
        headers: Dict[str, str] | None = None,
        **kwargs
    ) -> requests.Response | Page:
        """
        Request to go on this url only if we aren't already here.

        Arguments are optional parameters for url.

        >>> url = URL('https://exawple.org/(?P<pagename>).html')
        >>> url.stay_or_go(pagename='index')
        """
        assert self.browser is not None

        if self.is_here(**kwargs):
            return self.browser.page

        return self.go(params=params, data=data, json=json, method=method, headers=headers, **kwargs)

    def go(
        self,
        *,
        params: Dict | None = None,
        data: str | Dict | None = None,
        json: Dict | None = None,
        method: str | None = None,
        headers: Dict[str, str] |  None = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> requests.Response | Page:
        """
        Request to go on this url.

        Arguments are optional parameters for url.

        >>> url = URL('https://exawple.org/(?P<pagename>).html')
        >>> url.stay_or_go(pagename='index')
        """
        assert self.browser is not None

        headers = headers or {}
        if self._headers:
            headers.update(self._headers)

        if timeout is None:
            timeout = self._timeout

        r = self.browser.location(
            self.build(**kwargs),
            params=params,
            data=data,
            json=json,
            method=method,
            headers=headers,
            timeout=timeout,
        )
        return r.page or r

    def open(
        self,
        *,
        params: Dict | None = None,
        data: Dict | str | None = None,
        json: Dict | None = None,
        method: str | None = None,
        headers: Dict[str, str] | None = None,
        timeout: float | None = None,
        is_async: bool = False,
        callback: Callable[[requests.Response], requests.Response] = lambda response: response,
        **kwargs
    ) -> requests.Response | Page:
        """
        Request to open on this url.

        Arguments are optional parameters for url.

        >>> url = URL('https://exawple.org/(?P<pagename>).html')
        >>> url.open(pagename='index')
        """
        assert self.browser is not None

        headers = headers or {}
        if self._headers:
            headers.update(self._headers)

        if timeout is not None:
            timeout = self._timeout

        r = self.browser.open(
            self.build(**kwargs),
            params=params,
            data=data,
            json=json,
            method=method,
            headers=headers,
            is_async=is_async,
            callback=callback,
        )

        if hasattr(r, 'page') and r.page:
            return r.page
        return r

    def get_base_url(
        self,
        browser: Browser | None = None,
        for_pattern: str | None = None
    ) -> str:
        """
        Get the browser's base URL for the instance.

        ``for_pattern`` argument is optional and only used to display more
        information in the ValueError exception (don't know why, may be
        removed).
        """
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

    def build(self, **kwargs) -> str:
        """
        Build an url with the given arguments from URL's regexps.

        :param param: Query string parameters

        :rtype: :class:`str`
        :raises: :class:`UrlNotResolvable` if unable to resolve a correct url with the given arguments.
        """
        browser = kwargs.pop('browser', self.browser)

        assert browser is not None

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
                search = f'%({key})s'
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
                assert p.url is not None
                url = p.url
            return url

        raise UrlNotResolvable('Unable to resolve URL with %r. Available are %s' % (kwargs, ', '.join([pattern for pattern, _ in patterns])))

    def match(
        self, url: str,
        base: str | None = None
    ) -> re.Match | None:
        """
        Check if the given url match this object.

        Returns ``None`` if none matches.
        """
        for regex in self.urls:
            if not ABSOLUTE_URL_PATTERN_RE.match(regex):
                if not base:
                    base = self.get_base_url(browser=None, for_pattern=regex)

                regex = re.escape(base).rstrip('/') + '/' + regex.lstrip('/')

            m = re.match(regex, url)
            if m:
                return m

        return None

    def handle(self, response: requests.Response) -> Page | None:
        """
        Handle a HTTP response to get an instance of the klass if it matches.
        """
        assert self.browser is not None

        if self.klass is None:
            return None
        if response.request.method == 'HEAD':
            return None
        if self._methods and response.request.method not in self._methods:
            return None
        if self._content_type is not None:
            content_type = response.headers.get('Content-Type')
            if content_type is None:
                return None

            content_type, _, _ = content_type.partition(';')
            content_type = content_type.strip()
            if content_type != self._content_type:
                return None

        m = self.match(response.url)
        if m:
            page = self.klass(self.browser, response, m.groupdict())
            if hasattr(page, 'is_here'):
                if page.is_here is None or page.is_here is True:
                    return page
                elif page.is_here is False:
                    return None  # no page!
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

        return None

    def id2url(self, func: Callable):
        r"""
        Helper decorator to get an URL if the given first parameter is an ID.
        """

        @wraps(func)
        def inner(browser, id_or_url: str, *args, **kwargs):
            if re.match('^https?://.*', id_or_url):
                base = self.get_base_url(browser=browser)
                if not self.match(id_or_url, base=base):
                    return None
            else:
                id_or_url = self.build(id=id_or_url, browser=browser)

            return func(browser, id_or_url, *args, **kwargs)
        return inner

    def with_headers(
        self: URLType,
        headers: Optional[Dict[str, str]],
    ) -> URLType:
        """Get the current URL with different stored headers.

        For example, suppose that a browser needs to add an 'Accept'
        header for accessing a specific header of the API; see `Using the
        Accept Header to version your API`_ for more details.

        .. code-block:: python

            class MyBrowser(PagesBrowser):
                products = URL('products')

            class MyChildBrowser(MyBrowser):
                BASEURL = 'https://products-api.example/'

                products = MyBrowser.products.with_headers({
                    'Accept': 'application/vnd.example.api+json;version=2',
                })

        .. _`Using the Accept Header to version your API`:
            https://labs.qandidate.com/blog/2014/10/16/using-the-accept-header
            -to-version-your-api/

        :param headers: The new headers to set to the URL.
        :return: The URL using the different headers.
        """
        new_url = self.__class__(
            *self.urls,
            self.klass,
            base=self._base,
            headers=headers,
            timeout=self._timeout,
            methods=self._methods,
            content_type=self._content_type,
        )
        new_url.browser = None
        return new_url

    def without_headers(self: URLType) -> URLType:
        """Get the current URL without stored headers.

        :return: The URL using the different headers.
        """
        return self.with_headers(None)

    def with_timeout(self: URLType, timeout: Optional[float]) -> URLType:
        """Get a new URL object with timeout.

        :param timeout: The new timeout to apply, or ``None`` if the default
            timeout from the browser is to be used.
        :return: The URL using the different timeout.
        """
        new_url = self.__class__(
            *self.urls,
            self.klass,
            base=self._base,
            headers=self._headers,
            timeout=timeout,
            methods=self._methods,
            content_type=self._content_type,
        )
        new_url.browser = None
        return new_url

    def without_timeout(self: URLType) -> URLType:
        """Get a new URL object using the browser's timeout.

        :return: The URL without the custom timeout.
        """
        return self.with_timeout(None)

    def with_page(self: URLType, cls: Type[Page]) -> URLType:
        """Get a new URL with the same path but a different page class.

        :param cls: The new page class to use.
        :return: The URL object with the updated page class.
        """
        new_url = self.__class__(
            *self.urls,
            cls,
            base=self._base,
            headers=self._headers,
            timeout=self._timeout,
            methods=self._methods,
            content_type=self._content_type,
        )
        new_url.browser = None
        return new_url

    def with_urls(
        self: URLType,
        *urls: str,
        clear: bool = True,
        match_new_first: bool = True
    ) -> URLType:
        """Get a new URL object with the same page but with different paths.

        :param urls: List of urls handled by the page.
        :param clear: If True, the page will only handled the given urls.
            Otherwise, the urls are added to already handled urls.
        :param match_new_first: If true, new paths will be matched first
            for this URL; this parameter is ignored when ``clear`` is True.
        :return: The URL object with the updated patterns.
        """
        new_urls = list(urls)
        if not clear:
            # needed to extend self.urls which is a list
            if match_new_first:
                new_urls = new_urls + self.urls
            else:
                new_urls = self.urls + new_urls

        # We only want unique patterns here.
        new_urls = list(dict.fromkeys(new_urls))

        new_url = self.__class__(
            *new_urls,
            self.klass,
            base=self._base,
            headers=self._headers,
            timeout=self._timeout,
            methods=self._methods,
            content_type=self._content_type,
        )
        new_url.browser = None
        return new_url

    def with_base(
        self: URLType,
        base: str = 'BASEURL',
    ) -> URLType:
        """Get a new URL object with a custom base.

        :param base: The name of the new base, or None to use the default one.
        :return: The URL object with the updated base.
        """
        return self.__class__(
            *self.urls,
            self.klass,
            base=base,
            headers=self._headers,
            timeout=self._timeout,
            methods=self._methods,
            content_type=self._content_type,
        )

    def with_methods(
        self: URLType,
        methods: Tuple[str, ...],
    ) -> URLType:
        """Get a new URL object with custom methods.

        :param methods: The new methods to match the URL with.
        :return: The URL object with the updated methods.
        """
        return self.__class__(
            *self.urls,
            self.klass,
            base=self._base,
            headers=self._headers,
            timeout=self._timeout,
            methods=methods,
            content_type=self._content_type,
        )

    def without_methods(self: URLType) -> URLType:
        """Get a new URL object without matching on methods.

        :return: The URL object with the updated methods.
        """
        return self.with_methods(())

    def with_content_type(self: URLType, content_type: Optional[str]) -> URLType:
        """Get a new URL object with custom Content-Type matching.

        :param content_type: The new content type to match with.
        :return: The URL object with the updated content type to match.
        """
        return self.__class__(
            *self.urls,
            self.klass,
            base=self._base,
            headers=self._headers,
            timeout=self._timeout,
            methods=self._methods,
            content_type=content_type,
        )

    def without_content_type(self: URLType) -> URLType:
        """Get a new URL object without Content-Type matching.

        :return: The URL object with no content type matching.
        """
        return self.with_content_type(None)


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

    def build(self, **kwargs) -> str:
        prefix = 'browser_'

        for arg in kwargs:
            if arg.startswith(prefix):
                raise ValueError('parameter %r is reserved by URL pattern')

        for url in self.urls:
            for groupname in re.compile(url).groupindex:
                if groupname.startswith(prefix):
                    attrname = groupname[len(prefix):]
                    kwargs[groupname] = getattr(self.browser, attrname)

        return super().build(**kwargs)


def normalize_url(url: str) -> str:
    """Normalize URL by lower-casing the domain and other fixes.

    Lower-cases the domain, removes the default port and a trailing dot.

    >>> normalize_url('https://EXAMPLE:80')
    'https://example'
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
