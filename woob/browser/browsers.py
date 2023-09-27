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

from __future__ import annotations

from collections import OrderedDict
from functools import wraps
import importlib
import re
import base64
from hashlib import sha256
import zlib
from logging import Logger
from typing import Callable, Tuple, Type, Dict, Any, List, ClassVar

import os
from copy import copy, deepcopy
import inspect
from datetime import datetime, timedelta
from threading import Lock
from urllib.parse import urlparse, urljoin, urlencode, parse_qsl
import http
from uuid import uuid4
import warnings
import tempfile
import mimetypes

import urllib3
from dateutil import parser, tz
import requests

from woob.exceptions import (
    BrowserHTTPSDowngrade, BrowserRedirect, BrowserIncorrectPassword,
    BrowserUnavailable,
)
from woob.tools.date import now_as_utc
from woob.tools.log import getLogger
from woob.tools.json import json
from woob.tools.request import to_curl

from .adapters import HTTPAdapter
from .cookies import WoobCookieJar
from .exceptions import HTTPNotFound, ClientError, ServerError
from .har import HARManager
from .sessions import FuturesSession
from .profiles import Firefox, Profile
from .pages import NextPage
from .url import URL, normalize_url


class Browser:
    """
    Simple browser class.
    Acts like a browser, and doesn't try to do too much.

    >>> with Browser() as browser:
    ...     browser.open('https://example.org')
    ...
    <Response [200]>

    :param logger: parent logger (optional)
    :type logger: :py:class:`logging.Logger`
    :param proxy: use a proxy (dictionary with http/https as key and URI as value) (optional)
    :type proxy: dict
    :param responses_dirname: save responses to this directory (optional)
    :type responses_dirname: str
    :param proxy_headers: headers to supply to proxy (optional)
    :type proxy_headers: dict
    :param verify: either a boolean, in which case it controls whether we verify the server’s
        TLS certificate, or a string, in which case it must be a path to a CA bundle to use.
        Defaults will use the :attr:`Browser.VERIFY` attribute.
    :type verify: `None`, `bool` or `str`
    """

    PROFILE: ClassVar[Profile] = Firefox()
    """
    Default profile used by browser to navigate on websites.
    """

    TIMEOUT: ClassVar[float] = 10.0
    """
    Default timeout during requests.
    """

    REFRESH_MAX: ClassVar[float] = 0.0
    """
    When handling a Refresh header, the browsers considers it only if the sleep
    time in lesser than this value.
    """

    VERIFY: ClassVar[bool | str] = True
    """
    Check SSL certificates.

    If this is a string, path to the certificate or the CA bundle.

    Note that this value may be overriden by the ``verify`` argument on the
    constructor.
    """

    MAX_RETRIES: ClassVar[int] = 2
    """
    Maximum retries on failed requests.
    """

    MAX_WORKERS: ClassVar[int] = 10
    """
    Maximum of threads for asynchronous requests.
    """

    ALLOW_REFERRER: ClassVar[bool] = True
    """
    Controls how we send the ``Referer`` or not.

    If True, always allows the referers to be sent, False never, and None only
    if it is within the same domain.
    """

    HTTP_ADAPTER_CLASS: ClassVar[Type[HTTPAdapter]] = HTTPAdapter
    """
    Adapter class to use.
    """

    COOKIE_POLICY: ClassVar[http.cookiejar.CookiePolicy | None] = None
    """
    Default CookieJar policy.

    Example: :class:`~woob.browser.cookies.BlockAllCookies()`
    """

    @classmethod
    def asset(cls, localfile: str) -> str:
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

    def __init__(
        self,
        logger: Logger | None = None,
        proxy: Dict[str, str] | None = None,
        responses_dirname: str | None = None,
        proxy_headers: Dict[str, str] | None = None,
        woob: None = None,
        weboob: None = None,
        *,
        verify: bool | str | None = None,
    ):

        if woob is not None or weboob is not None:
            warnings.warn(
                "Don't use the 'woob' and 'weboob' parameters, they will be removed in woob 4.0",
                DeprecationWarning,
                stacklevel=2,
            )

        if logger:
            self.logger = getLogger("browser", logger)
        else:
            self.logger = getLogger("woob.browser")

        self.responses_dirname = responses_dirname
        self.responses_count = 0
        self.responses_lock = Lock()

        if self.logger.settings['ssl_insecure']:
            self.verify = False
        elif verify is not None:
            self.verify = verify
        else:
            self.verify = self.VERIFY

        if isinstance(self.verify, str):
            self.verify = self.asset(self.verify)

        self.PROXIES = proxy or {}
        self.proxy_headers = proxy_headers or {}
        self._setup_session(self.PROFILE)
        self.url: str | None = None
        self.response: requests.Response | None = None
        self.har_manager: HARManager | None = None

        if self.responses_dirname is not None:
            self.har_manager = HARManager(self.responses_dirname, self.logger)

    def deinit(self):
        """
        Deinitialisation of the browser.

        Call it when you stop to use the browser and you don't use it in a
        context manager.

        Can be overrided by any subclass which wants to cleanup after browser
        usage.
        """
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.deinit()

    def set_normalized_url(self, response: requests.Response, **kwargs):
        """
        Set the normalized URL on the response.

        :param response: the response to change
        :type response: :class:`requests.Response`
        """
        response.url = normalize_url(response.url)

    def save_response(self, response: requests.Response, warning: bool = False, **kwargs):
        """
        Save responses.

        By default it creates an HAR file and append request and response in.

        If ``WOOB_USE_OBSOLETE_RESPONSES_DIR`` is set to 1, it'll create a
        directory and all requests will be saved in three files:

        * ``0X-url-request.txt``
        * ``0X-url-response.txt``
        * ``0X-url.EXT``

        Information about which files are created is display in logs.

        Also if ``WOOB_CURLIFY_REQUEST`` is set to 1, ``0X-url-request.txt``
        will be filled with a ready to use curl command based on the request.

        :param response: the response to save
        :type response: :class:`requests.Response`
        :param warning: if True, display the saving logs as warnings (default to False)
        :type warning: bool
        """
        if self.responses_dirname is None:
            self.responses_dirname = tempfile.mkdtemp(prefix='woob_session_')

            self.logger.info('Debug data will be saved in this directory: %s', self.responses_dirname)
        elif not os.path.isdir(self.responses_dirname):
            os.makedirs(self.responses_dirname)

        if self.har_manager is None:
            self.har_manager = HARManager(self.responses_dirname, self.logger)

        slug = uuid4().hex

        with self.responses_lock:
            counter = self.responses_count
            self.responses_count += 1

        response_filepath = slug

        if os.environ.get('WOOB_USE_OBSOLETE_RESPONSES_DIR') == '1':
            # get the content-type, remove optionnal charset part
            mimetype = response.headers.get('Content-Type', '').split(';')[0]

            # try to get an extension (and avoid adding 'None')
            ext = mimetypes.guess_extension(mimetype, False) or ''

            filename = '%02d-%d-%s%s' % \
                (counter, response.status_code, slug, ext)

            response_filepath = os.path.join(self.responses_dirname, filename)

            request = response.request
            with open(response_filepath + '-request.txt', 'w', encoding='utf-8') as f:
                f.write('%s %s\n\n\n' % (request.method, request.url))

                for key, value in request.headers.items():
                    f.write('%s: %s\n' % (key, value))
                if request.body is not None:  # separate '' from None
                    body = request.body if isinstance(request.body, str) else request.body.decode()
                    f.write('\n\n\n%s' % body)
                if os.environ.get('WOOB_CURLIFY_REQUEST') == '1':
                    curl = to_curl(request)
                    f.write('\n\n' + curl + '\n')
            with open(response_filepath + '-response.txt', 'w', encoding='utf-8') as f:
                if hasattr(response.elapsed, 'total_seconds'):
                    f.write('Time: %3.3fs\n' % response.elapsed.total_seconds())
                f.write('%s %s\n\n\n' % (response.status_code, response.reason))
                for key, value in response.headers.items():
                    f.write('%s: %s\n' % (key, value))

            with open(response_filepath, 'wb') as f:
                f.write(response.content)

            match_filepath = os.path.join(self.responses_dirname, 'url_response_match.txt')
            with open(match_filepath, 'a', encoding='utf-8') as f:
                f.write('# %d %s %s\n' % (response.status_code, response.reason, response.headers.get('Content-Type', '')))
                f.write('%s\t%s\n' % (response.url, filename))

        self.har_manager.save_response(slug, response)

        msg = 'Response saved to %s'
        if warning:
            self.logger.warning(msg, response_filepath)
        else:
            self.logger.info(msg, response_filepath)

    def _save_request_to_har(self, request):
        assert self.har_manager is not None
        assert self.responses_dirname is not None

        # called when we don't have any response object
        if not os.path.isdir(self.responses_dirname):
            os.makedirs(self.responses_dirname)

        request_filepath = slug = uuid4().hex

        with self.responses_lock:
            counter = self.responses_count
            self.responses_count += 1

        time = self.TIMEOUT * 1000  # because TIMEOUT is in seconds, and we want milliseconds
        self.har_manager.save_request_only(slug, request, time)

        if os.environ.get('WOOB_USE_OBSOLETE_RESPONSES_DIR') == '1':
            request_filepath = os.path.join(
                self.responses_dirname,
                '%02d-000-%s-request.txt' % (counter, slug),
            )

            with open(request_filepath, 'w', encoding='utf-8') as f:
                f.write('%s %s\n\n\n' % (request.method, request.url))

                for key, value in request.headers.items():
                    f.write('%s: %s\n' % (key, value))

                if request.body is not None:  # separate '' from None
                    body = (
                        request.body if isinstance(request.body, str)
                        else request.body.decode()
                    )
                    f.write('\n\n\n%s' % body)

                if os.environ.get('WOOB_CURLIFY_REQUEST') == '1':
                    curl = to_curl(request)
                    f.write('\n\n' + curl + '\n')

        self.logger.info('Request saved to %s', request_filepath)

    def _create_session(self) -> requests.Session:
        return FuturesSession(
            max_workers=self.MAX_WORKERS, max_retries=self.MAX_RETRIES,
            adapter_class=self.HTTP_ADAPTER_CLASS,
        )

    def _setup_session(self, profile: Profile):
        """
        Set up a python3-requests session for our usage.
        """
        session = self._create_session()

        session.proxies = self.PROXIES

        session.verify = self.verify

        if not session.verify:
            try:
                urllib3.disable_warnings()
            except AttributeError:
                # urllib3 is too old, warnings won't be disable
                pass

        adapter_kwargs: Dict[str, Any] = {}

        # defines a max_retries. It's mandatory in case a server is not
        # handling keep alive correctly, like the proxy burp
        adapter_kwargs['max_retries'] = self.MAX_RETRIES

        adapter_kwargs['proxy_headers'] = self.proxy_headers

        # set connection pool size equal to MAX_WORKERS if needed
        if self.MAX_WORKERS > requests.adapters.DEFAULT_POOLSIZE:
            adapter_kwargs['pool_connections'] = self.MAX_WORKERS
            adapter_kwargs['pool_maxsize'] = self.MAX_WORKERS

        session.mount('http://', self.HTTP_ADAPTER_CLASS(**adapter_kwargs))
        session.mount('https://', self.HTTP_ADAPTER_CLASS(**adapter_kwargs))

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

    def set_profile(self, profile: Profile):
        """
        Update the profile of the session.
        """
        profile.setup_session(self.session)

    def location(self, url: str | requests.Request, **kwargs) -> requests.Response:
        """
        Like :meth:`open()` but also changes the current URL and response.
        This is the most common method to request web pages.

        Other than that, has the exact same behavior of :meth:`open()`.
        """
        assert not kwargs.get('is_async'), "Please use open() instead of location() to make asynchronous requests."
        response = self.open(url, **kwargs)
        self.response = response
        self.url = self.response.url
        return response

    def open(
        self,
        url: str | requests.Request,
        *,
        referrer: str | None = None,
        allow_redirects: bool = True,
        stream: bool | None = None,
        timeout: float | None = None,
        verify: str | bool | None = None,
        cert: str | Tuple[str, str] | None = None,
        proxies: Dict | None = None,
        data_encoding: str | None = None,
        is_async: bool = False,
        callback: Callable[[requests.Response], requests.Response] | None = None,
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request like a browser does:
         * follow redirects (unless disabled)
         * provide referrers (unless disabled)

        Unless a ``method`` is explicitly provided, it makes a GET request,
        or a POST if data is not None,
        An empty ``data`` (like ``''`` or ``{}``, not ``None``) *will* make a POST.

        It is a wrapper around session.request().
        All ``session.request()`` options are available.
        You should use :meth:`location()` or :meth:`open()` and not ``session.request()``,
        since it has some interesting additions, which are easily individually
        disabled through the arguments.

        Call this instead of :meth:`location()` if you do not want to "visit" the URL
        (for instance, you are downloading a file).

        When ``is_async`` is ``True``, :meth:`open()` returns a :py:class:`~concurrent.futures.Future` object (see
        :py:mod:`concurrent.futures` for more details), which can be evaluated with its
        :py:meth:`~concurrent.futures.Future.result()` method. If any exception is raised while processing request,
        it is caught and re-raised when calling :py:meth:`~concurrent.futures.Future.result()`.

        For example:

        >>> Browser().open('https://google.com', is_async=True).result().text # doctest: +SKIP

        :param url: URL
        :param params: (optional) Dictionary, list of tuples or bytes to send
            in the query string
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body
        :param json: (optional) A JSON serializable Python object to send in the body
        :param headers: (optional) Dictionary of HTTP Headers to send
        :param cookies: (optional) Dict or CookieJar object to send
        :param files: (optional) Dictionary of ``'name': file-like-objects`` (or ``{'name': file-tuple}``) for multipart encoding upload.
            ``file-tuple`` can be a 2-tuple ``('filename', fileobj)``, 3-tuple ``('filename', fileobj, 'content_type')``
            or a 4-tuple ``('filename', fileobj, 'content_type', custom_headers)``, where ``'content-type'`` is a string
            defining the content type of the given file and ``custom_headers`` a dict-like object containing additional headers
            to add for the file.
        :param auth: (optional) Auth tuple to enable Basic/Digest/Custom HTTP Auth.

        :param referrer: (optional) Force referrer. False to disable sending it, None for guessing
        :type referrer: str or False or None

        :param allow_redirects: (optional) if ``True``, follow HTTP redirects (default: ``True``)
        :type allow_redirects: bool

        :param stream: (optional) if ``False``, the response content will be immediately downloaded.
        :param timeout: (optional) How many seconds to wait for the server to send data
                        before giving up, as a float, or a tuple.
        :type timeout: float or tuple
        :param verify: (optional) Either a boolean, in which case it controls whether we verify
                the server's TLS certificate, or a string, in which case it must be a path
                to a CA bundle to use. If not provided, uses the :attr:`Browser.VERIFY` class attribute value, the
                :attr:`Browser.verify` attribute one, or ``True``.
        :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.
        :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.

        :param is_async: (optional) Process request in a non-blocking way (default: ``False``)
        :type is_async: bool

        :param callback: (optional) Callback to be called when request has finished,
                         with response as its first and only argument
        :type callback: callable

        :return: :class:`requests.Response <Response>` object
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
            verify = self.verify

        if timeout is None:
            timeout = self.TIMEOUT
        if callback is None:
            callback = lambda response: response

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
            if not already_handled_exception and self.responses_dirname is not None and self.har_manager is not None:
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

    def async_open(self, url: str, **kwargs) -> requests.Response:
        """
        Shortcut to open(url, is_async=True).
        """
        if 'async' in kwargs:
            del kwargs['async']
        if 'is_async' in kwargs:
            del kwargs['is_async']
        return self.open(url, is_async=True, **kwargs)

    def raise_for_status(self, response: requests.Response):
        """
        Like :meth:`requests.Response.raise_for_status()` but will use other
        exception specific classes:

        * :class:`~woob.browser.exceptions.HTTPNotFound` for 404
        * :class:`~woob.browser.exceptions.ClientError` for 4xx errors
        * :class:`~woob.browser.exceptions.ServerError` for 5xx errors
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

    def build_request(
        self,
        url: str | requests.Request,
        *,
        referrer: str | None = None,
        data_encoding: str | None = None,
        **kwargs
    ) -> requests.Request:
        """
        Does the same job as :meth:`open()`, but returns a :class:`~requests.Request` without
        submitting it.
        This allows further customization to the :class:`~requests.Request`.
        """

        url_string: str
        if isinstance(url, requests.Request):
            req = url
            url_string = req.url
        elif isinstance(url, str):
            req = requests.Request(url=url, **kwargs)
            url_string = url
        else:
            raise TypeError('"url" must be a string or a requests.Request object.')

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
                encoded_value: Any
                if isinstance(v, str):
                    encoded_value = v.encode(data_encoding)
                elif isinstance(v, list):
                    encoded_value = [
                        element.encode(data_encoding) if isinstance(element, str) else element for element in v
                    ]
                else:
                    encoded_value = v
                encoded_data[k] = encoded_value
            req.data = encoded_data

        if referrer is None:
            referrer = self.get_referrer(self.url, url_string)
        if referrer:
            # Yes, it is a misspelling.
            req.headers.setdefault('Referer', referrer)

        return req

    def prepare_request(self, req: requests.Request) -> requests.PreparedRequest:
        """
        Get a prepared request from a :class:`~requests.Request` object.

        This method aims to be overloaded by children classes.
        """
        return self.session.prepare_request(req)

    REFRESH_RE = re.compile(r"^(?P<sleep>[\d\.]+)(;\s*url=[\"']?(?P<url>.*?)[\"']?)?$", re.IGNORECASE)

    def handle_refresh(self, response: requests.Response) -> requests.Response:
        """
        Called by open, to handle Refresh HTTP header.

        It only redirect to the refresh URL if the sleep time is inferior to
        :attr:`REFRESH_MAX`.
        """
        if 'Refresh' not in response.headers:
            return response

        m = self.REFRESH_RE.match(response.headers['Refresh'])
        if m:
            # XXX perhaps we should not redirect if the refresh url is equal to the current url.
            url = m.groupdict().get('url', None) or response.request.url
            sleep = float(m.groupdict()['sleep'])

            assert isinstance(url, str)

            if sleep <= self.REFRESH_MAX:
                self.logger.debug('Refresh to %s', url)
                return self.open(url)
            else:
                self.logger.debug('Do not refresh to %s because %s > REFRESH_MAX(%s)', url, sleep, self.REFRESH_MAX)
                return response

        self.logger.warning('Unable to handle refresh "%s"', response.headers['Refresh'])

        return response

    def get_referrer(self, oldurl: str | None, newurl: str) -> str | None:
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
            return None
        if oldurl is None:
            return None
        old = urlparse(oldurl)
        new = urlparse(newurl)
        # Do not leak secure URLs to insecure URLs
        if old.scheme == 'https' and new.scheme != 'https':
            return None
        # Reloading the page. Usually no referrer.
        if oldurl == newurl:
            return None
        # Domain-based privacy
        if self.ALLOW_REFERRER is None and old.netloc != new.netloc:
            return None
        return oldurl

    def export_session(self) -> dict:
        """
        Export session into a dict.

        Default format is::

            {
                'url': last_url,
                'cookies': cookies_dict
            }

        You should store it as is.
        """
        # XXX similar to StatesMixin, should be merged?
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
    Raises by :class:`DomainBrowser` when :attr:`~DomainBrowser.RESTRICT_URL` is set and trying to go
    on an url not matching :attr:`~DomainBrowser.BASEURL`.
    """


class DomainBrowser(Browser):
    """
    A browser that handles relative URLs and can have a base URL (usually a domain).

    For instance ``self.location('/hello')`` will get https://woob.tech/hello
    if :attr:`BASEURL` is ``'https://woob.tech/'``.

    >>> class ExampleBrowser(DomainBrowser):
    ...     BASEURL = 'https://example.org'
    ...
    >>> with ExampleBrowser() as browser:
    ...     browser.open('/')
    ...
    <Response [200]>
    """

    BASEURL: str | None = None
    """
    Base URL, e.g. ``'https://woob.tech/'``.

    See :meth:`absurl()`.
    """

    RESTRICT_URL: ClassVar[bool | List[str]] = False
    """
    URLs allowed to load.
    This can be used to force SSL (if the :attr:`BASEURL` is SSL) or any other leakage.
    Set to ``True`` to allow only URLs starting by the :attr:`BASEURL`.
    Set it to a list of allowed URLs if you have multiple allowed URLs.
    More complex behavior is possible by overloading :meth:`url_allowed()`.
    """

    def __init__(
        self,
        baseurl: str | None = None,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        if baseurl is not None:
            self.BASEURL = baseurl

    def url_allowed(self, url: str) -> bool:
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

    def absurl(self, uri: str, base: str | bool | None = None) -> str:
        """
        Get the absolute URL, relative to a base URL.
        If base is ``None``, it will try to use the current URL.
        If there is no current URL, it will try to use :attr:`BASEURL`.

        If base is ``False``, it will always try to use the current URL.
        If base is ``True``, it will always try to use BASEURL.

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

    def open(self, url: requests.Request | str, *args, **kwargs) -> requests.Response:
        """
        Like :meth:`Browser.open` but handles urls without domains, using
        the :attr:`BASEURL` attribute.
        """
        if isinstance(url, requests.Request):
            req = url
            req_url = req.url
        else:
            req = None
            req_url = url

        abs_url = self.absurl(req_url)
        if not self.url_allowed(abs_url):
            raise UrlNotAllowed(abs_url)

        if req:
            req.url = abs_url
            url = req
        else:
            url = abs_url
        return super().open(url, *args, **kwargs)

    def go_home(self) -> requests.Response:
        """
        Go to the "home" page, usually the BASEURL.
        """
        return self.location(self.BASEURL or self.absurl('/'))


class PagesBrowser(DomainBrowser):
    r"""
    A browser which works pages and keep state of navigation.

    To use it, you have to derive it and to create :class:`~woob.browser.url.URL` objects as class attributes. When
    :meth:`open()` or :meth:`location()` are called, if the url matches one of :class:`~woob.browser.url.URL` objects, it returns a
    :class:`~woob.browser.pages.Page` object. In case of :meth:`location()`, it stores it in ``self.page``.

    Example:

        >>> import re
        >>> from .pages import HTMLPage
        >>> class ListPage(HTMLPage):
        ...     def get_items(self):
        ...         for link in self.doc.xpath('//a[matches(@href, "list-\d+.html")]/@href'):
        ...             yield re.match('list-(\d+).html', link).group(1)
        ...
        >>> class ItemPage(HTMLPage):
        ...     def iter_values(self):
        ...         for el in self.doc.xpath('//li'):
        ...             yield el.text
        ...
        >>> class MyBrowser(PagesBrowser):
        ...     BASEURL = 'https://woob.tech/tests/'
        ...     list = URL(r'$', ListPage)
        ...     item = URL(r'list-(?P<id>\d+)\.html', ItemPage)
        ...
        >>> b = MyBrowser()
        >>> b.list.go()
        <woob.browser.browsers.ListPage object at 0x...>
        >>> b.page.url
        'https://woob.tech/tests/'
        >>> list(b.page.get_items())
        ['1', '2']
        >>> b.item.build(id=42)
        'https://woob.tech/tests/list-42.html'
        >>> b.item.go(id=1)
        <woob.browser.browsers.ItemPage object at 0x...>
        >>> list(b.page.iter_values())
        ['One', 'Two']
    """

    _urls = None

    def __init__(self, *args, **kwargs):
        self._urls = OrderedDict()
        self.highlight_el = kwargs.pop('highlight_el', False)
        super().__init__(*args, **kwargs)

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

    def open(self, *args, **kwargs) -> requests.Response:
        """
        Same method than
        :meth:`~woob.browser.browsers.DomainBrowser.open`, but the
        response contains an attribute ``page`` if the url matches any
        :class:`~woob.browser.url.URL` object.
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

    def location(self, *args, **kwargs) -> requests.Response:
        """
        Same method than :meth:`~woob.browser.browsers.Browser.location`, but
        if the url matches any :class:`~woob.browser.url.URL` object, an
        attribute ``page`` is added to response, and the attribute :attr:`page`
        is set on the browser.
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

    def pagination(self, func: Callable, *args, **kwargs):
        r"""
        This helper function can be used to handle pagination pages easily.

        When the called function raises an exception :class:`~woob.browser.pages.NextPage`, it goes
        on the wanted page and recall the function.

        :class:`~woob.browser.pages.NextPage` constructor can take an url or a Request object.

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

        .. note: consider using :func:`~woob.browser.pages.pagination` decorator instead.
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
    ``logged`` attribute in the current browser's page: when this
    attribute is set to ``True`` (e.g., when the page inherits
    :class:`~woob.browser.pages.LoggedPage`), then nothing special happens.

    In all other cases (when the browser isn't on any defined page or
    when the page's ``logged`` attribute is ``False``), the
    :meth:`LoginBrowser.do_login` method of the browser is called before
    calling :`func`.
    """

    @wraps(func)
    def inner(browser: LoginBrowser, *args, **kwargs):
        if (
            (
                not hasattr(browser, 'logged') or
                (
                    hasattr(browser, 'logged') and
                    not browser.logged
                )
            ) and (
                not hasattr(browser, 'page') or
                browser.page is None or
                not browser.page.logged
            )
        ):
            browser.do_login()
            if browser.logger.settings.get('export_session'):
                browser.logger.debug('logged in with session: %s', json.dumps(browser.export_session()))
        return func(browser, *args, **kwargs)

    return inner


class LoginBrowser(PagesBrowser):
    """
    A browser which supports login.
    """

    def __init__(self, username: str, password: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class StatesMixin:
    """
    Mixin to store states of browser.

    It saves and loads a ``state`` dict object. By default it contains the
    current url and cookies, but may be overriden by the subclass to store its
    specific stuff.
    """

    __states__: ClassVar[Tuple[str, ...]] = ()
    """
    Saved state variables.
    """

    STATE_DURATION: ClassVar[int | float | None] = None
    """
    In minutes, used to set an expiration datetime object of the state.
    """

    def locate_browser(self, state: dict):
        """
        From the ``state`` object, go on the saved url.
        """
        try:
            self.location(state['url'])
        except (requests.exceptions.HTTPError, requests.exceptions.TooManyRedirects):
            pass

    def _load_cookies(self, cookie_state: str):
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

    def load_state(self, state: dict):
        """
        Supply a ``state`` object and load it.
        """
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

    def get_expire(self) -> str | None:
        """
        Get expiration of the ``state`` object, using the :attr:`STATE_DURATION` class attribute.
        """
        if self.STATE_DURATION is None:
            return None

        return str((now_as_utc() + timedelta(minutes=self.STATE_DURATION)).replace(microsecond=0))

    def dump_state(self) -> dict:
        """
        Dump the current state in a ``state`` object.

        Can be overloaded by the browser subclass.
        """
        # XXX similar to Browser.export_session, should be merged, or use it?
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

    def build_request(self, *args, **kwargs) -> requests.Request:
        if 'data' in kwargs and isinstance(kwargs['data'], dict):
            kwargs['data'] = json.dumps(kwargs['data'])
        if 'headers' not in kwargs:
            kwargs['headers'] = {}
        kwargs['headers']['Content-Type'] = 'application/json'

        return super().build_request(*args, **kwargs)

    def open(self, *args, **kwargs) -> requests.Response:
        """
        Do a JSON request.

        The "Content-Type" header is always set to "application/json".

        :param data: if specified, format as JSON and send as request body
        :type data: dict
        :param headers: if specified, add these headers to the request
        :type headers: dict
        """
        return super().open(*args, **kwargs)

    def request(self, *args, **kwargs) -> requests.Response:
        """
        Do a JSON request and parse the response.

        :returns: a dict containing the parsed JSON server response
        :rtype: dict
        """
        return self.open(*args, **kwargs).json()


class AbstractBrowserMissingParentError(Exception):
    """
    .. deprecated:: 3.4
       Don't use this class, import woob_modules.other_module.etc instead
    """


class MetaBrowser(type):
    """
    .. deprecated:: 3.4
       Don't use this class, import woob_modules.other_module.etc instead
    """

    _parent_attr_re = re.compile(r'^[^.]+\.(.*)\.([^.]+)$')

    def __new__(mcs, name, bases, dct):
        from woob.tools.backend import Module  # Here to avoid file wide circular dependency

        if name != 'AbstractBrowser' and AbstractBrowser in bases:
            warnings.warn(
                'AbstractBrowser is deprecated and will be removed in woob 4.0. '
                'Use standard "from woob_modules.other_module import Browser" instead.',
                DeprecationWarning,
                stacklevel=2
            )

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

        return super().__new__(mcs, name, bases, dct)


class AbstractBrowser(metaclass=MetaBrowser):
    """
    .. deprecated:: 3.4
       Don't use this class, import woob_modules.other_module.etc instead
    """


class OAuth2Mixin(StatesMixin):
    AUTHORIZATION_URI: ClassVar[str, None] = None
    """
    OAuth2 Authorization URI.
    """

    ACCESS_TOKEN_URI: ClassVar[str, None] = None
    """
    OAuth2 route to exchange a code with an access_token.
    """

    SCOPE: ClassVar[str] = ''
    """
    OAuth2 scope.
    """

    client_id: str | None = None
    client_secret: str | None = None
    redirect_uri: str | None = None
    access_token: str | None = None
    access_token_expire: datetime | None = None
    auth_uri: str | None = None
    token_type: str | None = None
    refresh_token: str | None = None
    oauth_state: str | None = None
    authorized_date: str | None = None
    callback_error_description = (
       'operation canceled by the client',
       'login cancelled',
       'consent denied',
       'psu cancelled the transaction',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__states__ += (
            'access_token', 'refresh_token', 'token_type',
        )

    def build_request(self, *args, **kwargs) -> requests.Request:
        headers = kwargs.setdefault('headers', {})
        if self.access_token:
            headers['Authorization'] = '{} {}'.format(self.token_type, self.access_token)
        return super().build_request(*args, **kwargs)

    def dump_state(self) -> dict:
        state = super().dump_state()

        if self.authorized_date:
            state['authorized_date'] = str(self.authorized_date)
        if self.access_token_expire:
            state['access_token_expire'] = self.access_token_expire.isoformat()

        return state

    def load_state(self, state: dict):
        def load_date_or_none(date_str):
            if date_str:
                date_converted = parser.parse(date_str)
                if isinstance(date_converted, datetime):
                    return date_converted
            return None

        super().load_state(state)
        self.authorized_date = load_date_or_none(state.get('authorized_date'))
        self.access_token_expire = load_date_or_none(state.get('access_token_expire'))
        if self.access_token_expire and not self.access_token_expire.tzinfo:
            self.access_token_expire = self.access_token_expire.replace(tzinfo=tz.tzlocal())

    def raise_for_status(self, response: requests.Response):
        if response.status_code == 401:
            self.access_token = None

        return super().raise_for_status(response)

    @property
    def logged(self) -> bool:
        # 'access_token_expire' is already set as UTC in OAuth2Mixin.update_token.
        return self.access_token is not None and (not self.access_token_expire or self.access_token_expire > now_as_utc())

    def do_login(self):
        if self.refresh_token:
            self.use_refresh_token()
        elif self.auth_uri:
            self.request_access_token(self.auth_uri)
        else:
            self.request_authorization()

    def build_authorization_parameters(self) -> dict:
        params = {
            'redirect_uri':    self.redirect_uri,
            'scope':           self.SCOPE,
            'client_id':       self.client_id,
            'response_type':   'code',
        }
        if self.oauth_state:
            params['state'] = self.oauth_state
        return params

    def build_authorization_uri(self) -> str:
        if self.AUTHORIZATION_URI is None:
            self.logger.warning('Use AUTHORIZATION_URI which is None')

        p = urlparse(self.AUTHORIZATION_URI)
        q = dict(parse_qsl(p.query))
        q.update(self.build_authorization_parameters())
        return p._replace(query=urlencode(q)).geturl()

    def request_authorization(self):
        self.logger.info('request authorization')
        raise BrowserRedirect(self.build_authorization_uri())

    def handle_callback_error(self, values: dict):
        callback_error_description = re.compile('|'.join(self.callback_error_description))

        error = values.get('error')
        error_message = values.get('error_description')

        if error == 'access_denied':
            if error_message:
                if callback_error_description.search(error_message.lower()):
                    raise BrowserIncorrectPassword(error_message)
                raise AssertionError(f'Unhandled callback error_message: {error_message}')
            # access_denied with no error message
            raise BrowserIncorrectPassword()
        if error == 'server_error':
            raise BrowserUnavailable()
        raise AssertionError(f'Unhandled callback error: {error}, error_message: {error_message}')

    def build_access_token_parameters(self, values: dict) -> dict:
        return {
            'code': values['code'],
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }

    def do_token_request(self, data):
        if self.ACCESS_TOKEN_URI is None:
            self.logger.warning('Use ACCESS_TOKEN_URI which is None')

        return self.open(self.ACCESS_TOKEN_URI, data=data)

    def request_access_token(self, auth_uri: str | Dict):
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

    def build_refresh_token_parameters(self) -> dict:
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

    def update_token(self, auth_response: dict):
        self.token_type = auth_response.get('token_type', 'Bearer').capitalize() # don't know yet if this is a good idea, but required by bnpstet
        if 'refresh_token' in auth_response:
            self.refresh_token = auth_response['refresh_token']
        self.access_token = auth_response['access_token']
        self.access_token_expire = now_as_utc() + timedelta(seconds=int(auth_response['expires_in']))


class OAuth2PKCEMixin(OAuth2Mixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__states__ += ('pkce_verifier', 'pkce_challenge')
        self.pkce_verifier = self.code_verifier()
        self.pkce_challenge = self.code_challenge(self.pkce_verifier)

    # PKCE (Proof Key for Code Exchange) standard protocol methods:
    def code_verifier(self, bytes_number: int = 64) -> str:
        return base64.urlsafe_b64encode(os.urandom(bytes_number)).rstrip(b'=').decode('ascii')

    def code_challenge(self, verifier: str) -> str:
        digest = sha256(verifier.encode('utf8')).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

    def build_authorization_parameters(self) -> dict:
        params = {
            'redirect_uri': self.redirect_uri,
            'code_challenge_method': 'S256',
            'code_challenge': self.pkce_challenge,
            'client_id': self.client_id,
        }
        if self.oauth_state:
            params['state'] = self.oauth_state
        return params

    def build_access_token_parameters(self, values: dict) -> dict:
        return {
            'code': values['code'],
            'grant_type': 'authorization_code',
            'code_verifier': self.pkce_verifier,
            'redirect_uri': self.redirect_uri,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }


class DigestMixin:
    """Browser mixin to add a ``Digest`` header compliant with RFC 3230 section 4.3.2."""

    HTTP_DIGEST_ALGORITHM: str = 'SHA-256'
    """Digest algorithm used to obtain a hash of the request content.

    The only supported digest algorithm for now is 'SHA-256'.
    """

    HTTP_DIGEST_METHODS: tuple[str, ...] | None = ('GET', 'POST', 'PUT', 'DELETE')
    """The list of HTTP methods on which to add a ``Digest`` header.

    To add the ``Digest`` header to all methods, set this constant to None.
    """

    HTTP_DIGEST_COMPACT_JSON: bool = False
    """If the content type of the request payload is JSON, compact it first."""

    def compute_digest_header(self, body: bytes) -> str:
        """Compute the value of the ``Digest`` header.

        :param body: The body to compute with.
        :return: The computed ``Digest`` header value.
        """
        if self.HTTP_DIGEST_ALGORITHM == 'SHA-256':
            return 'SHA-256=' + base64.b64encode(sha256(body).digest()).decode()

        raise ValueError(f'Unhandled digest algorithm {self.HTTP_DIGEST_ALGORITHM!r}')

    def add_digest_header(self, preq: requests.PreparedRequest) -> None:
        """Add the ``Digest`` header to the prepared request.

        The ``Digest`` header presence depends on the request:

        - If the request has a ``HTTP_DIGEST_INCLUDE`` header, the ``Digest`` header is added.
        - Otherwise, if the request has a ``HTTP_DIGEST_EXCLUDE`` header, the ``Digest`` header is not added.
        - Otherwise, if :attr:`HTTP_DIGEST_METHOD` is an HTTP method list and the request method is not in said list,
          the ``Digest`` header is not added.
        - Otherwise, the ``Digest`` header is added.

        Note that the ``HTTP_DIGEST_INCLUDE`` and ``HTTP_DIGEST_EXCLUDE`` headers are removed from the request before
        sending it.

        :param preq: The prepared request on which the ``Digest`` header is added.

        .. code-block:: python

            class MyBrowser(DigestMixin, Browser):
                HTTP_DIGEST_METHODS = ('POST', 'PUT', 'DELETE')

            my_browser = MyBrowser()
            my_browser.open('https://example.org/')
        """
        digest_include = preq.headers.pop('HTTP_DIGEST_INCLUDE', None) is not None
        digest_exclude = preq.headers.pop('HTTP_DIGEST_EXCLUDE', None) is not None

        allowed_digest_method = (
            self.HTTP_DIGEST_METHODS is None
            or preq.method in self.HTTP_DIGEST_METHODS
        )

        if not (allowed_digest_method or digest_include) or digest_exclude:
            return

        body = preq.body or b''
        if isinstance(body, str):
            body = body.encode('utf-8')

        if self.HTTP_DIGEST_COMPACT_JSON:
            if 'application/json' in preq.headers.get('Content-Type', ''):
                body = json.dumps(json.loads(body), separators=(',', ':')).encode('utf-8')

        preq.headers['Digest'] = self.compute_digest_header(body)

    def prepare_request(self, *args, **kwargs) -> requests.PreparedRequest:
        """
        Get the prepared request with a ``Digest`` header.
        """
        preq = super().prepare_request(*args, **kwargs)
        self.add_digest_header(preq)
        return preq
