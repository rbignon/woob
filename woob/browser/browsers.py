# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021 Romain Bignon
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

from __future__ import absolute_import, print_function

from collections import OrderedDict
from functools import wraps
import importlib
import re
import base64
from hashlib import sha256
import zlib
try:
    from requests.packages import urllib3
except ImportError:
    import urllib3
import os
import sys
from copy import copy, deepcopy
import inspect
from datetime import datetime, timedelta
from dateutil import parser, tz
from threading import Lock
from urllib.parse import urlparse, urljoin, urlencode, parse_qsl
from uuid import uuid4

import requests

from woob.exceptions import (
    BrowserHTTPSDowngrade, BrowserRedirect, BrowserIncorrectPassword,
    BrowserUnavailable,
)

from woob.tools.date import now_as_utc
from woob.tools.log import getLogger
from woob.tools.json import json

from .adapters import HTTPAdapter
from .cookies import WoobCookieJar
from .exceptions import HTTPNotFound, ClientError, ServerError
from .har import HARManager
from .sessions import FuturesSession
from .profiles import Firefox
from .pages import NextPage
from .url import URL, normalize_url


class Browser(object):
    """
    Simple browser class.
    Act like a browser, and don't try to do too much.
    """

    PROFILE = Firefox()
    """
    Default profile used by browser to navigate on websites.
    """

    TIMEOUT = 10.0
    """
    Default timeout during requests.
    """

    REFRESH_MAX = 0.0
    """
    When handling a Refresh header, the browsers considers it only if the sleep
    time in lesser than this value.
    """

    VERIFY = True
    """
    Check SSL certificates.
    """

    MAX_RETRIES = 2
    """
    Maximum retries on failed requests.
    """

    MAX_WORKERS = 10
    """
    Maximum of threads for asynchronous requests.
    """

    ALLOW_REFERRER = True
    """
    Controls the behavior of get_referrer.
    """

    HTTP_ADAPTER_CLASS = HTTPAdapter

    COOKIE_POLICY = None
    """
    Default CookieJar policy.
    Example: woob.browser.cookies.BlockAllCookies()
    """

    @classmethod
    def asset(cls, localfile):
        """
        Absolute file path for a module local file.
        """
        if os.path.isabs(localfile):
            return localfile
        return os.path.join(os.path.dirname(inspect.getfile(cls)), localfile)

    def __new__(cls, *args, **kwargs):
        """ Accept any arguments, necessary for AbstractBrowser __new__ override.

        AbstractBrowser, in its overridden __new__, removes itself from class hierarchy
        so its __new__ is called only once. In python 3, default (object) __new__ is
        then used for next instantiations but it's a slot/"fixed" version supporting
        only one argument (type to instanciate).
        """
        return object.__new__(cls)

    def __init__(self, logger=None, proxy=None, responses_dirname=None, woob=None, proxy_headers=None, weboob=None):
        if logger:
            self.logger = getLogger("browser", logger)
        else:
            self.logger = getLogger("woob.browser")

        self.responses_dirname = responses_dirname
        self.responses_count = 0
        self.responses_lock = Lock()

        if isinstance(self.VERIFY, str):
            self.VERIFY = self.asset(self.VERIFY)

        self.PROXIES = proxy
        self.proxy_headers = proxy_headers or {}
        self._setup_session(self.PROFILE)
        self.url = None
        self.response = None
        self.har_manager = None

        if self.responses_dirname is not None:
            self.har_manager = HARManager(self.responses_dirname, self.logger)

    def deinit(self):
        self.session.close()

    def set_normalized_url(self, response, **kwargs):
        response.url = normalize_url(response.url)

    def save_response(self, response, warning=False, **kwargs):
        if self.responses_dirname is None:
            import tempfile
            self.responses_dirname = tempfile.mkdtemp(prefix='woob_session_')
            self.har_manager = HARManager(self.responses_dirname, self.logger)
            print('Debug data will be saved in this directory: %s' % self.responses_dirname, file=sys.stderr)
        elif not os.path.isdir(self.responses_dirname):
            os.makedirs(self.responses_dirname)

        slug = uuid4().hex

        with self.responses_lock:
            counter = self.responses_count
            self.responses_count += 1

        response_filepath = slug

        if os.environ.get('WOOB_USE_OBSOLETE_RESPONSES_DIR') == '1':
            import mimetypes
            # get the content-type, remove optionnal charset part
            mimetype = response.headers.get('Content-Type', '').split(';')[0]
            # due to http://bugs.python.org/issue1043134
            if mimetype == 'text/plain':
                ext = '.txt'
            else:
                # try to get an extension (and avoid adding 'None')
                ext = mimetypes.guess_extension(mimetype, False) or ''

            filename = '%02d-%d-%s%s' % \
                (counter, response.status_code, slug, ext)

            response_filepath = os.path.join(self.responses_dirname, filename)

            request = response.request
            with open(response_filepath + '-request.txt', 'w') as f:
                f.write('%s %s\n\n\n' % (request.method, request.url))

                for key, value in request.headers.items():
                    f.write('%s: %s\n' % (key, value))
                if request.body is not None:  # separate '' from None
                    body = request.body if isinstance(request.body, str) else request.body.decode()
                    f.write('\n\n\n%s' % body)
            with open(response_filepath + '-response.txt', 'w') as f:
                if hasattr(response.elapsed, 'total_seconds'):
                    f.write('Time: %3.3fs\n' % response.elapsed.total_seconds())
                f.write('%s %s\n\n\n' % (response.status_code, response.reason))
                for key, value in response.headers.items():
                    f.write('%s: %s\n' % (key, value))

            with open(response_filepath, 'wb') as f:
                f.write(response.content)

            match_filepath = os.path.join(self.responses_dirname, 'url_response_match.txt')
            with open(match_filepath, 'a') as f:
                f.write('# %d %s %s\n' % (response.status_code, response.reason, response.headers.get('Content-Type', '')))
                f.write('%s\t%s\n' % (response.url, filename))

        self.har_manager.save_response(slug, response)

        msg = u'Response saved to %s' % response_filepath
        if warning:
            self.logger.warning(msg)
        else:
            self.logger.info(msg)

    def _save_request_to_har(self, request):
        # called when we don't have any response object
        if not os.path.isdir(self.responses_dirname):
            os.makedirs(self.responses_dirname)

        slug = uuid4().hex
        time = self.TIMEOUT * 1000  # because TIMEOUT is in seconds, and we want milliseconds
        self.har_manager.save_request_only(slug, request, time)
        self.logger.warning(u'Request saved to %s' % slug)

    def _create_session(self):
        return FuturesSession(
            max_workers=self.MAX_WORKERS, max_retries=self.MAX_RETRIES,
            adapter_class=self.HTTP_ADAPTER_CLASS,
        )

    def _setup_session(self, profile):
        """
        Set up a python3-requests session for our usage.
        """
        session = self._create_session()

        session.proxies = self.PROXIES

        session.verify = not self.logger.settings['ssl_insecure'] and self.VERIFY
        if not session.verify:
            try:
                urllib3.disable_warnings()
            except AttributeError:
                # urllib3 is too old, warnings won't be disable
                pass

        # defines a max_retries. It's mandatory in case a server is not
        # handling keep alive correctly, like the proxy burp
        adapter_kwargs = dict(max_retries=self.MAX_RETRIES,
                              proxy_headers=self.proxy_headers)
        # set connection pool size equal to MAX_WORKERS if needed
        if self.MAX_WORKERS > requests.adapters.DEFAULT_POOLSIZE:
            adapter_kwargs.update(pool_connections=self.MAX_WORKERS,
                                  pool_maxsize=self.MAX_WORKERS)
        session.mount('https://', self.HTTP_ADAPTER_CLASS(**adapter_kwargs))
        session.mount('http://', self.HTTP_ADAPTER_CLASS(**adapter_kwargs))

        if self.TIMEOUT:
            session.timeout = self.TIMEOUT
        ## woob only can provide proxy and HTTP auth options
        session.trust_env = False

        profile.setup_session(session)

        session.hooks['response'].append(self.set_normalized_url)
        if self.responses_dirname is not None:
            session.hooks['response'].append(self.save_response)

        self.session = session

        session.cookies = WoobCookieJar()
        if self.COOKIE_POLICY:
            session.cookies.set_policy(self.COOKIE_POLICY)

    def set_profile(self, profile):
        profile.setup_session(self.session)

    def location(self, url, **kwargs):
        """
        Like :meth:`open` but also changes the current URL and response.
        This is the most common method to request web pages.

        Other than that, has the exact same behavior of open().
        """
        assert not kwargs.get('is_async'), "Please use open() instead of location() to make asynchronous requests."
        response = self.open(url, **kwargs)
        self.response = response
        self.url = self.response.url
        return response

    def open(self, url, *, referrer=None,
                   allow_redirects=True,
                   stream=None,
                   timeout=None,
                   verify=None,
                   cert=None,
                   proxies=None,
                   data_encoding=None,
                   is_async=False,
                   callback=lambda response: response,
                   **kwargs):
        """
        Make an HTTP request like a browser does:
         * follow redirects (unless disabled)
         * provide referrers (unless disabled)

        Unless a `method` is explicitly provided, it makes a GET request,
        or a POST if data is not None,
        An empty `data` (not None, like '' or {}) *will* make a POST.

        It is a wrapper around session.request().
        All session.request() options are available.
        You should use location() or open() and not session.request(),
        since it has some interesting additions, which are easily
        individually disabled through the arguments.

        Call this instead of location() if you do not want to "visit" the URL
        (for instance, you are downloading a file).

        When `is_async` is True, open() returns a Future object (see
        concurrent.futures for more details), which can be evaluated with its
        result() method. If any exception is raised while processing request,
        it is caught and re-raised when calling result().

        For example:

        >>> Browser().open('http://google.com', is_async=True).result().text # doctest: +SKIP

        :param url: URL
        :type url: str

        :param data: POST data
        :type url: str or dict or None

        :param referrer: Force referrer. False to disable sending it, None for guessing
        :type referrer: str or False or None

        :param is_async: Process request in a non-blocking way
        :type is_async: bool

        :param callback: Callback to be called when request has finished,
                         with response as its first and only argument
        :type callback: function

        :rtype: :class:`requests.Response`
        """

        if isinstance(url, str):
            url = normalize_url(url)
        elif isinstance(url, requests.Request):
            url.url = normalize_url(url.url)

        req = self.build_request(url, referrer=referrer, data_encoding=data_encoding, **kwargs)
        preq = self.prepare_request(req)

        if hasattr(preq, '_cookies'):
            # The _cookies attribute is not present in requests < 2.2. As in
            # previous version it doesn't calls extract_cookies_to_jar(), it is
            # not a problem as we keep our own cookiejar instance.
            preq._cookies = WoobCookieJar.from_cookiejar(preq._cookies)
            if self.COOKIE_POLICY:
                preq._cookies.set_policy(self.COOKIE_POLICY)

        if proxies is None:
            proxies = self.PROXIES

        if verify is None:
            verify = not self.logger.settings['ssl_insecure'] and self.VERIFY

        if timeout is None:
            timeout = self.TIMEOUT

        # We define an inner_callback here in order to execute the same code
        # regardless of is_async param.
        def inner_callback(future, response):
            if allow_redirects:
                response = self.handle_refresh(response)

            self.raise_for_status(response)
            return callback(response)

        # call python3-requests
        try:
            response = self.session.send(preq,
                                         allow_redirects=allow_redirects,
                                         stream=stream,
                                         timeout=timeout,
                                         verify=verify,
                                         cert=cert,
                                         proxies=proxies,
                                         callback=inner_callback,
                                         is_async=is_async)
        except Exception as error:
            # response in these kind of exception are already stored in HAR
            # skip them to not store response twice
            already_handled_exception = any(
                isinstance(error, exc) for exc in (HTTPNotFound, ClientError, ServerError)
            )
            if not already_handled_exception and self.responses_dirname is not None:
                # when timeout or any kind of exception occur
                # we don't have any response given by python-requests
                # but we still need to store request to HAR
                if isinstance(error, requests.exceptions.RequestException):
                    if error.response is not None:
                        slug = uuid4().hex
                        self.har_manager.save_response(slug, error.response)
                    elif error.request:
                        # some exceptions raised by python-requests don't even provide request
                        # we prefer use error.request because python3-requests may modify request
                        # by calling add_headers() to it, but it won't happens if
                        # requests.adapters.HTTPAdapter.add_headers() is not overwritten
                        self._save_request_to_har(error.request)
                    else:
                        # use preq request if the exception doesn't provide the request
                        self._save_request_to_har(preq)
                # don't store request for other exceptions, it can be anything
                # but in that case request has already been stored in HAR file
            raise
        return response

    def async_open(self, url, **kwargs):
        """
        Shortcut to open(url, is_async=True).
        """
        if 'async' in kwargs:
            del kwargs['async']
        if 'is_async' in kwargs:
            del kwargs['is_async']
        return self.open(url, is_async=True, **kwargs)

    def raise_for_status(self, response):
        """
        Like Response.raise_for_status but will use other classes if needed.
        """
        if 400 <= response.status_code < 500:
            http_error_msg = '%s Client Error: %s' % (response.status_code, response.reason)
            if response.status_code == 404:
                raise HTTPNotFound(http_error_msg, response=response)
            raise ClientError(http_error_msg, response=response)
        elif 500 <= response.status_code < 600:
            http_error_msg = '%s Server Error: %s' % (response.status_code, response.reason)
            raise ServerError(http_error_msg, response=response)

        # in case we did not catch something that should be
        response.raise_for_status()

    def build_request(self, url, *, referrer=None, data_encoding=None, **kwargs):
        """
        Does the same job as open(), but returns a Request without
        submitting it.
        This allows further customization to the Request.
        """
        if isinstance(url, requests.Request):
            req = url
            url = req.url
        else:
            req = requests.Request(url=url, **kwargs)

        # guess method
        if req.method is None:
            # 'data' and 'json' (even if empty) are (always?) passed to build_request
            # and None is their default. For a Request object, the defaults are different.
            # Request.json is None and Request.data == [] by default.
            # Could they break unexpectedly?
            if (
                req.data or kwargs.get('data') is not None
                or req.json or kwargs.get('json') is not None
            ):
                req.method = 'POST'
            else:
                req.method = 'GET'

        # convert unicode strings to proper encoding
        if isinstance(req.data, str) and data_encoding:
            req.data = req.data.encode(data_encoding)
        if isinstance(req.data, dict) and data_encoding:
            encoded_data = OrderedDict()
            for k, v in req.data.items():
                if isinstance(v, str):
                    encoded_v = v.encode(data_encoding)
                elif isinstance(v, list):
                    encoded_v = [
                        element.encode(data_encoding) if isinstance(element, str) else element for element in v
                    ]
                else:
                    encoded_v = v
                encoded_data[k] = encoded_v
            req.data = encoded_data

        if referrer is None:
            referrer = self.get_referrer(self.url, url)
        if referrer:
            # Yes, it is a misspelling.
            req.headers.setdefault('Referer', referrer)

        return req

    def prepare_request(self, req):
        """
        Get a prepared request from a Request object.

        This method aims to be overloaded by children classes.
        """
        return self.session.prepare_request(req)

    REFRESH_RE = re.compile(r"^(?P<sleep>[\d\.]+)(;\s*url=[\"']?(?P<url>.*?)[\"']?)?$", re.IGNORECASE)

    def handle_refresh(self, response):
        """
        Called by open, to handle Refresh HTTP header.

        It only redirect to the refresh URL if the sleep time is inferior to
        REFRESH_MAX.
        """
        if 'Refresh' not in response.headers:
            return response

        m = self.REFRESH_RE.match(response.headers['Refresh'])
        if m:
            # XXX perhaps we should not redirect if the refresh url is equal to the current url.
            url = m.groupdict().get('url', None) or response.request.url
            sleep = float(m.groupdict()['sleep'])

            if sleep <= self.REFRESH_MAX:
                self.logger.debug('Refresh to %s' % url)
                return self.open(url)
            else:
                self.logger.debug('Do not refresh to %s because %s > REFRESH_MAX(%s)' % (url, sleep, self.REFRESH_MAX))
                return response

        self.logger.warning('Unable to handle refresh "%s"' % response.headers['Refresh'])

        return response

    def get_referrer(self, oldurl, newurl):
        """
        Get the referrer to send when doing a request.
        If we should not send a referrer, it will return None.

        Reference: https://en.wikipedia.org/wiki/HTTP_referer

        The behavior can be controlled through the ALLOW_REFERRER attribute.
        True always allows the referers
        to be sent, False never, and None only if it is within
        the same domain.

        :param oldurl: Current absolute URL
        :type oldurl: str or None

        :param newurl: Target absolute URL
        :type newurl: str

        :rtype: str or None
        """
        if self.ALLOW_REFERRER is False:
            return
        if oldurl is None:
            return
        old = urlparse(oldurl)
        new = urlparse(newurl)
        # Do not leak secure URLs to insecure URLs
        if old.scheme == 'https' and new.scheme != 'https':
            return
        # Reloading the page. Usually no referrer.
        if oldurl == newurl:
            return
        # Domain-based privacy
        if self.ALLOW_REFERRER is None and old.netloc != new.netloc:
            return
        return oldurl

    def export_session(self):
        def make_cookie(c):
            d = {
                k: getattr(c, k) for k in ['name', 'value', 'domain', 'path', 'secure']
            }
            #d['session'] = c.discard
            d['httpOnly'] = 'httponly' in [k.lower() for k in c._rest.keys()]
            d['expirationDate'] = getattr(c, 'expires', None)
            return d

        return {
            'url': self.url,
            'cookies': [make_cookie(c) for c in self.session.cookies],
        }


class UrlNotAllowed(Exception):
    """
    Raises by :class:`DomainBrowser` when `RESTRICT_URL` is set and trying to go
    on an url not matching `BASEURL`.
    """


class DomainBrowser(Browser):
    """
    A browser that handles relative URLs and can have a base URL (usually a domain).

    For instance self.location('/hello') will get http://woob.tech/hello
    if BASEURL is 'http://woob.tech/'.
    """

    BASEURL = None
    """
    Base URL, e.g. 'http://woob.tech/' or 'https://woob.tech/'
    See absurl().
    """

    RESTRICT_URL = False
    """
    URLs allowed to load.
    This can be used to force SSL (if the BASEURL is SSL) or any other leakage.
    Set to True to allow only URLs starting by the BASEURL.
    Set it to a list of allowed URLs if you have multiple allowed URLs.
    More complex behavior is possible by overloading url_allowed()
    """

    def __init__(self, baseurl=None, *args, **kwargs):
        super(DomainBrowser, self).__init__(*args, **kwargs)
        if baseurl is not None:
            self.BASEURL = baseurl

    def url_allowed(self, url):
        """
        Checks if we are allowed to visit an URL.
        See RESTRICT_URL.

        :param url: Absolute URL
        :type url: str
        :rtype: bool
        """
        if self.BASEURL is None or self.RESTRICT_URL is False:
            return True
        if self.RESTRICT_URL is True:
            return url.startswith(self.BASEURL)
        for restrict_url in self.RESTRICT_URL:
            if url.startswith(restrict_url):
                return True
        return False

    def absurl(self, uri, base=None):
        """
        Get the absolute URL, relative to a base URL.
        If base is None, it will try to use the current URL.
        If there is no current URL, it will try to use BASEURL.

        If base is False, it will always try to use the current URL.
        If base is True, it will always try to use BASEURL.

        :param uri: URI to make absolute. It can be already absolute.
        :type uri: str

        :param base: Base absolute URL.
        :type base: str or None or False or True

        :rtype: str
        """
        if not base:
            base = self.url
        if base is None or base is True:
            base = self.BASEURL
        return urljoin(base, uri)

    def open(self, req, *args, **kwargs):
        """
        Like :meth:`Browser.open` but handles urls without domains, using
        the :attr:`BASEURL` attribute.
        """
        uri = req.url if isinstance(req, requests.Request) else req

        url = self.absurl(uri)
        if not self.url_allowed(url):
            raise UrlNotAllowed(url)

        if isinstance(req, requests.Request):
            req.url = url
        else:
            req = url
        return super(DomainBrowser, self).open(req, *args, **kwargs)

    def go_home(self):
        """
        Go to the "home" page, usually the BASEURL.
        """
        return self.location(self.BASEURL or self.absurl('/'))


class PagesBrowser(DomainBrowser):
    r"""
    A browser which works pages and keep state of navigation.

    To use it, you have to derive it and to create URL objects as class
    attributes. When open() or location() are called, if the url matches
    one of URL objects, it returns a Page object. In case of location(), it
    stores it in self.page.

    Example:

    >>> from .pages import HTMLPage
    >>> class ListPage(HTMLPage):
    ...     def get_items():
    ...         return [el.attrib['id'] for el in self.doc.xpath('//div[@id="items"]/div')]
    ...
    >>> class ItemPage(HTMLPage):
    ...     pass
    ...
    >>> class MyBrowser(PagesBrowser):
    ...     BASEURL = 'http://example.org/'
    ...     list = URL('list-items', ListPage)
    ...     item = URL('item/view/(?P<id>\d+)', ItemPage)
    ...
    >>> MyBrowser().list.stay_or_go().get_items() # doctest: +SKIP
    >>> bool(MyBrowser().list.match('http://example.org/list-items'))
    True
    >>> bool(MyBrowser().list.match('http://example.org/'))
    False
    >>> str(MyBrowser().item.build(id=42))
    'http://example.org/item/view/42'

    You can then use URL instances to go on pages.
    """

    _urls = None

    def __init__(self, *args, **kwargs):
        self._urls = OrderedDict()
        self.highlight_el = kwargs.pop('highlight_el', False)
        super(PagesBrowser, self).__init__(*args, **kwargs)

        self.page = None

        # exclude properties because they can access other fields not yet defined
        def is_property(attr):
            v = getattr(type(self), attr, None)
            return hasattr(v, '__get__') or hasattr(v, '__set__')

        attrs = [(attr, getattr(self, attr)) for attr in dir(self) if not is_property(attr)]
        attrs = [v for v in attrs if isinstance(v[1], URL)]
        attrs.sort(key=lambda v: v[1]._creation_counter)
        for k, v in deepcopy(attrs):
            self._urls[k] = v
            setattr(self, k, v)
        for url in self._urls.values():
            url.browser = self

    def __setattr__(self, key, value):
        if isinstance(self._urls, OrderedDict):
            # _urls is instanciated, we can now feed it accordingly.
            if isinstance(value, URL):
                # We want to either replace in-place, or add to the URLs.
                if key in self._urls:
                    # We want to actually make the old URL unusable.
                    self._urls[key].browser = None

                value = copy(value)
                value.browser = self
                self._urls[key] = value
            elif key in self._urls:
                # We want to remove the URL from our mapping only.
                url = self._urls.pop(key)
                url.browser = None

        super().__setattr__(key, value)

    def __delattr__(self, key):
        if isinstance(self._urls, OrderedDict):
            if key in self._urls:
                # We want to remove the URL from our mapping.
                del self._urls[key]

        super().__delattr__(key)

    def open(self, *args, **kwargs):
        """
        Same method than
        :meth:`woob.browser.browsers.DomainBrowser.open`, but the
        response contains an attribute `page` if the url matches any
        :class:`URL` object.
        """

        callback = kwargs.pop('callback', lambda response: response)
        page_class = kwargs.pop('page', None)

        # Have to define a callback to seamlessly process synchronous and
        # asynchronous requests, see :meth:`Browser.open` and its `is_async`
        # and `callback` params.
        def internal_callback(response):
            # Try to handle the response page with an URL instance.
            response.page = None
            if page_class:
                response.page = page_class(self, response)
                return callback(response)

            for url in self._urls.values():
                response.page = url.handle(response)
                if response.page is not None:
                    self.logger.debug('Handle %s with %s', response.url, response.page.__class__.__name__)
                    break

            if response.page is None:
                regexp = r'^(?P<proto>\w+)://.*'

                proto_response = re.match(regexp, response.url)
                if proto_response and self.BASEURL:
                    proto_response = proto_response.group('proto')
                    proto_base = re.match(regexp, self.BASEURL).group('proto')

                    if proto_base == 'https' and proto_response != 'https':
                        raise BrowserHTTPSDowngrade()

                self.logger.debug('Unable to handle %s', response.url)

            return callback(response)

        return super(PagesBrowser, self).open(callback=internal_callback, *args, **kwargs)

    def location(self, *args, **kwargs):
        """
        Same method than
        :meth:`woob.browser.browsers.Browser.location`, but if the
        url matches any :class:`URL` object, an attribute `page` is added to
        response, and the attribute :attr:`PagesBrowser.page` is set.
        """
        if self.page is not None:
            # Call leave hook.
            self.page.on_leave()

        response = self.open(*args, **kwargs)

        self.response = response
        self.page = response.page
        self.url = response.url

        if self.page is not None:
            # Call load hook.
            self.page.on_load()

        # Returns self.response in case on_load recalls location()
        return self.response

    def pagination(self, func, *args, **kwargs):
        r"""
        This helper function can be used to handle pagination pages easily.

        When the called function raises an exception :class:`NextPage`, it goes
        on the wanted page and recall the function.

        :class:`NextPage` constructor can take an url or a Request object.

        >>> from .pages import HTMLPage
        >>> class Page(HTMLPage):
        ...     def iter_values(self):
        ...         for el in self.doc.xpath('//li'):
        ...             yield el.text
        ...         for next in self.doc.xpath('//a'):
        ...             raise NextPage(next.attrib['href'])
        ...
        >>> class Browser(PagesBrowser):
        ...     BASEURL = 'https://woob.tech'
        ...     list = URL('/tests/list-(?P<pagenum>\d+).html', Page)
        ...
        >>> b = Browser()
        >>> b.list.go(pagenum=1) # doctest: +ELLIPSIS
        <woob.browser.browsers.Page object at 0x...>
        >>> list(b.pagination(lambda: b.page.iter_values()))
        ['One', 'Two', 'Three', 'Four']
        """
        while True:
            try:
                for r in func(*args, **kwargs):
                    yield r
            except NextPage as e:
                self.location(e.request)
            else:
                return


def need_login(func):
    """
    Decorator used to require to be logged to access to this function.

    This decorator can be used on any method whose first argument is a
    browser (typically a :class:`LoginBrowser`). It checks for the
    `logged` attribute in the current browser's page: when this
    attribute is set to ``True`` (e.g., when the page inherits
    :class:`LoggedPage`), then nothing special happens.

    In all other cases (when the browser isn't on any defined page or
    when the page's `logged` attribute is ``False``), the
    :meth:`LoginBrowser.do_login` method of the browser is called before
    calling :`func`.
    """

    @wraps(func)
    def inner(browser, *args, **kwargs):
        if (not hasattr(browser, 'logged') or (hasattr(browser, 'logged') and not browser.logged)) and \
                (not hasattr(browser, 'page') or browser.page is None or not browser.page.logged):
            browser.do_login()
            if browser.logger.settings.get('export_session'):
                browser.logger.debug('logged in with session: %s', json.dumps(browser.export_session()))
        return func(browser, *args, **kwargs)

    return inner


class LoginBrowser(PagesBrowser):
    """
    A browser which supports login.
    """

    def __init__(self, username, password, *args, **kwargs):
        super(LoginBrowser, self).__init__(*args, **kwargs)
        self.username = username
        self.password = password

    def do_login(self):
        """
        Abstract method to implement to login on website.

        It is called when a login is needed.
        """
        raise NotImplementedError()

    def do_logout(self):
        """
        Logout from website.

        By default, simply clears the cookies.
        """
        self.session.cookies.clear()


class StatesMixin(object):
    """
    Mixin to store states of browser.
    """

    __states__ = ()
    """
    Saved state variables.
    """

    STATE_DURATION = None
    """
    In minutes, used to set an expiration datetime object of the state.
    """

    def locate_browser(self, state):
        try:
            self.location(state['url'])
        except (requests.exceptions.HTTPError, requests.exceptions.TooManyRedirects):
            pass

    def _load_cookies(self, cookie_state):
        try:
            uncompressed = zlib.decompress(base64.b64decode(cookie_state))
        except (TypeError, zlib.error, EOFError, ValueError):
            self.logger.error('Unable to uncompress cookies from storage')
            return

        try:
            jcookies = json.loads(uncompressed)
        except ValueError:
            self.logger.error('Unable to reload cookies from storage')
        else:
            for jcookie in jcookies:
                self.session.cookies.set(**jcookie)
            self.logger.debug('Reloaded cookies from storage')

    def load_state(self, state):
        expire = state.get('expire')

        if expire:
            expire = parser.parse(expire)
            if not expire.tzinfo:
                expire = expire.replace(tzinfo=tz.tzlocal())
            if expire < now_as_utc():
                self.logger.info('State expired, not reloading it from storage')
                return

        if 'cookies' in state:
            self._load_cookies(state['cookies'])

        for attrname in self.__states__:
            if attrname in state:
                setattr(self, attrname, state[attrname])

        if 'url' in state:
            self.locate_browser(state)

    def get_expire(self):
        return str((now_as_utc() + timedelta(minutes=self.STATE_DURATION)).replace(microsecond=0))

    def dump_state(self):
        state = {}
        if hasattr(self, 'page') and self.page:
            state['url'] = self.page.url

        cookies = [
            {
                attr: getattr(cookie, attr)
                for attr in ('name', 'value', 'domain', 'path', 'secure', 'expires')
            }
            for cookie in self.session.cookies
        ]
        state['cookies'] = base64.b64encode(zlib.compress(json.dumps(cookies).encode('utf-8'))).decode('ascii')
        for attrname in self.__states__:
            try:
                state[attrname] = getattr(self, attrname)
            except AttributeError:
                pass
        if self.STATE_DURATION is not None:
            state['expire'] = self.get_expire()
        self.logger.debug('Stored cookies into storage')
        return state


class APIBrowser(DomainBrowser):
    """
    A browser for API websites.
    """

    def build_request(self, *args, **kwargs):
        if 'data' in kwargs and isinstance(kwargs['data'], dict):
            kwargs['data'] = json.dumps(kwargs['data'])
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers']['Content-Type'] = 'application/json'

        return super(APIBrowser, self).build_request(*args, **kwargs)

    def open(self, *args, **kwargs):
        """
        Do a JSON request.

        The "Content-Type" header is always set to "application/json".

        :param data: if specified, format as JSON and send as request body
        :type data: :class:`dict`
        :param headers: if specified, add these headers to the request
        :type headers: :class:`dict`
        """
        return super(APIBrowser, self).open(*args, **kwargs)

    def request(self, *args, **kwargs):
        """
        Do a JSON request and parse the response.

        :returns: a dict containing the parsed JSON server response
        :rtype: :class:`dict`
        """
        return self.open(*args, **kwargs).json()


class AbstractBrowserMissingParentError(Exception):
    pass


class MetaBrowser(type):
    # we can remove this class as soon as we get rid of Abstract*

    _parent_attr_re = re.compile(r'^[^.]+\.(.*)\.([^.]+)$')

    def __new__(mcs, name, bases, dct):
        from woob.tools.backend import Module  # Here to avoid file wide circular dependency

        if name != 'AbstractBrowser' and AbstractBrowser in bases:
            parent_attr = dct.get('PARENT_ATTR')
            if parent_attr:
                m = MetaBrowser._parent_attr_re.match(parent_attr)
                path, klass_name = m.group(1, 2)
                module = importlib.import_module('woob_modules.%s.%s' % (dct['PARENT'], path))
                klass = getattr(module, klass_name)
            else:
                module = importlib.import_module('woob_modules.%s' % dct['PARENT'])
                for attrname in dir(module):
                    attr = getattr(module, attrname)
                    if isinstance(attr, type) and issubclass(attr, Module) and attr != Module:
                        klass = attr.BROWSER
                        break

            bases = tuple(klass if isinstance(base, mcs) else base for base in bases)

        return super(MetaBrowser, mcs).__new__(mcs, name, bases, dct)


class AbstractBrowser(metaclass=MetaBrowser):
    """Don't use this class, import woob_modules.other_module.etc instead"""


class OAuth2Mixin(StatesMixin):
    AUTHORIZATION_URI = None
    ACCESS_TOKEN_URI = None
    SCOPE = ''

    client_id = None
    client_secret = None
    redirect_uri = None
    access_token = None
    access_token_expire = None
    auth_uri = None
    token_type = None
    refresh_token = None
    oauth_state = None
    authorized_date = None

    def __init__(self, *args, **kwargs):
        super(OAuth2Mixin, self).__init__(*args, **kwargs)
        self.__states__ += (
            'access_token', 'refresh_token', 'token_type',
        )

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})
        if self.access_token:
            headers['Authorization'] = '{} {}'.format(self.token_type, self.access_token)
        return super(OAuth2Mixin, self).build_request(*args, **kwargs)

    def dump_state(self):
        state = super(OAuth2Mixin, self).dump_state()

        if self.authorized_date:
            state['authorized_date'] = str(self.authorized_date)
        if self.access_token_expire:
            state['access_token_expire'] = self.access_token_expire.isoformat()

        return state

    def load_state(self, state):
        def load_date_or_none(date_str):
            if date_str:
                date_converted = parser.parse(date_str)
                if isinstance(date_converted, datetime):
                    return date_converted
            return None

        super(OAuth2Mixin, self).load_state(state)
        self.authorized_date = load_date_or_none(state.get('authorized_date'))
        self.access_token_expire = load_date_or_none(state.get('access_token_expire'))
        if self.access_token_expire and not self.access_token_expire.tzinfo:
            self.access_token_expire = self.access_token_expire.replace(tzinfo=tz.tzlocal())

    def raise_for_status(self, response):
        if response.status_code == 401:
            self.access_token = None

        return super(OAuth2Mixin, self).raise_for_status(response)

    @property
    def logged(self):
        # 'access_token_expire' is already set as UTC in OAuth2Mixin.update_token.
        return self.access_token is not None and (not self.access_token_expire or self.access_token_expire > now_as_utc())

    def do_login(self):
        if self.refresh_token:
            self.use_refresh_token()
        elif self.auth_uri:
            self.request_access_token(self.auth_uri)
        else:
            self.request_authorization()

    def build_authorization_parameters(self):
        params = {
            'redirect_uri':    self.redirect_uri,
            'scope':           self.SCOPE,
            'client_id':       self.client_id,
            'response_type':   'code',
        }
        if self.oauth_state:
            params['state'] = self.oauth_state
        return params

    def build_authorization_uri(self):
        p = urlparse(self.AUTHORIZATION_URI)
        q = dict(parse_qsl(p.query))
        q.update(self.build_authorization_parameters())
        return p._replace(query=urlencode(q)).geturl()

    def request_authorization(self):
        self.logger.info('request authorization')
        raise BrowserRedirect(self.build_authorization_uri())

    def handle_callback_error(self, values):
        wrongpass_on_webauth_errors = re.compile('|'.join((
            'operation canceled by the client',
            'login cancelled',
            'consent denied',
            'psu cancelled the transaction',
        )))

        error = values.get('error')
        error_message = values.get('error_description')

        if error == 'access_denied':
            if error_message:
                if wrongpass_on_webauth_errors.search(error_message.lower()):
                    raise BrowserIncorrectPassword(error_message)
                raise AssertionError(f'Unhandled callback error_message: {error_message}')
            # access_denied with no error message
            raise BrowserIncorrectPassword()
        if error == 'server_error':
            raise BrowserUnavailable()
        raise AssertionError(f'Unhandled callback error: {error}, error_message: {error_message}')

    def build_access_token_parameters(self, values):
        return {
            'code': values['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

    def do_token_request(self, data):
        return self.open(self.ACCESS_TOKEN_URI, data=data)

    def request_access_token(self, auth_uri):
        self.logger.info('requesting access token')

        if isinstance(auth_uri, dict):
            values = auth_uri
        else:
            values = dict(parse_qsl(urlparse(auth_uri).query))
        if not values.get('code'):
            self.handle_callback_error(values)
        self.authorized_date = now_as_utc()
        data = self.build_access_token_parameters(values)
        try:
            auth_response = self.do_token_request(data).json()
        except ClientError:
            raise AssertionError('PSU has successfully logged in, but the request to get an access token failed.')

        self.update_token(auth_response)

    def build_refresh_token_parameters(self):
        return {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
        }

    def use_refresh_token(self):
        self.logger.info('refreshing token')

        data = self.build_refresh_token_parameters()
        try:
            auth_response = self.do_token_request(data).json()
        except ClientError:
            self.refresh_token = None
            raise BrowserIncorrectPassword()

        self.update_token(auth_response)

    def update_token(self, auth_response):
        self.token_type = auth_response.get('token_type', 'Bearer').capitalize() # don't know yet if this is a good idea, but required by bnpstet
        if 'refresh_token' in auth_response:
            self.refresh_token = auth_response['refresh_token']
        self.access_token = auth_response['access_token']
        self.access_token_expire = now_as_utc() + timedelta(seconds=int(auth_response['expires_in']))


class OAuth2PKCEMixin(OAuth2Mixin):
    def __init__(self, *args, **kwargs):
        super(OAuth2PKCEMixin, self).__init__(*args, **kwargs)
        self.__states__ += ('pkce_verifier', 'pkce_challenge')
        self.pkce_verifier = self.code_verifier()
        self.pkce_challenge = self.code_challenge(self.pkce_verifier)

    # PKCE (Proof Key for Code Exchange) standard protocol methods:
    def code_verifier(self, bytes_number=64):
        return base64.urlsafe_b64encode(os.urandom(bytes_number)).rstrip(b'=').decode('ascii')

    def code_challenge(self, verifier):
        digest = sha256(verifier.encode('utf8')).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

    def build_authorization_parameters(self):
        params = {
            'redirect_uri': self.redirect_uri,
            'code_challenge_method': 'S256',
            'code_challenge': self.pkce_challenge,
            'client_id': self.client_id,
        }
        if self.oauth_state:
            params['state'] = self.oauth_state
        return params

    def build_access_token_parameters(self, values):
        return {
            'code': values['code'],
            'grant_type': 'authorization_code',
            'code_verifier': self.pkce_verifier,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
