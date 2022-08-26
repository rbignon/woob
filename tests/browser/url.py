# -*- coding: utf-8 -*-
# Copyright(C) 2014 Julia Leven
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

from unittest import TestCase

from woob.browser import PagesBrowser, URL
from woob.browser.pages import Page
from woob.browser.url import BrowserParamURL, UrlNotResolvable, normalize_url


class MyMockBrowserWithoutBrowser(object):
    BASEURL = "http://woob.tech/"
    absolute_url = URL(r'https://example.org/absolute-url')
    relative_url = URL(r'/relative-url')


# Mock that allows to represent a Page
class MyMockPage(Page):
    pass


# Mock that allows to represent a Browser
class MyMockBrowser(PagesBrowser):
    BASEURL = "http://woob.tech/"

    # URL used by method match
    urlNotRegex = URL("http://test.org/", "http://test2.org/")
    urlRegex = URL("http://test.org/", "http://woob2.org/")
    urlRegWithoutHttp = URL("news")
    urlNotRegWithoutHttp = URL("youtube")

    # URL used by method build
    urlValue = URL(r"http://test.com/(?P<id>\d+)")
    urlParams = URL(r"http://test.com/\?id=(?P<id>\d+)&name=(?P<name>.+)")
    urlSameParams = URL(r"http://test.com/(?P<id>\d+)", r"http://test.com\?id=(?P<id>\d+)&name=(?P<name>.+)")

    # URL used by method is_here
    urlIsHere = URL('http://woob.tech/(?P<param>)', MyMockPage)
    urlIsHereDifKlass = URL('http://free.fr/', MyMockPage)


# Class that tests different methods from the class URL
class TestURL(TestCase):

    # Initialization of the objects needed by the tests
    def setUp(self):
        self.myBrowser = MyMockBrowser()
        self.myBrowserWithoutBrowser = MyMockBrowserWithoutBrowser()

    # Check that an assert is sent if both base and browser are none
    def test_match_base_none_browser_none(self):
        self.assertRaises(ValueError,
                          self.myBrowserWithoutBrowser.relative_url.match,
                          "http://woob.tech/")

    def test_match_base_none_browser_none_absolute(self):
        """Check matching an absolute URL with no browser."""
        self.myBrowserWithoutBrowser.absolute_url.match('http://woob.tech/')

    # Check that no assert is raised when browser is none and a base is indeed
    # instantiated when given as a parameter
    def test_match_base_not_none_browser_none(self):
        try:
            self.myBrowserWithoutBrowser.relative_url.match(
                'http://woob.tech/news',
                base='http://woob.tech/',
            )
        except ValueError:
            self.fail(
                'Method match returns a ValueError while '
                + 'base parameter is not none!',
            )

    def test_match_base_not_none_browser_none_absolute(self):
        self.myBrowserWithoutBrowser.absolute_url.match('http://woob.tech/')

    # Check that none is returned when none of the defined urls is a regex for
    # the given url
    def test_match_url_pasregex_baseurl(self):
        res = self.myBrowser.urlNotRegex.match("http://woob.tech/news")
        self.assertIsNone(res)

    # Check that true is returned when one of the defined urls is a regex
    # for the given url
    def test_match_url_regex_baseurl(self):
        res = self.myBrowser.urlRegex.match("http://woob2.org/news")
        self.assertTrue(res)

    # Successful test with relatives url
    def test_match_url_without_http(self):
        res = self.myBrowser.urlRegWithoutHttp.match("http://woob.tech/news")
        self.assertTrue(res)

    # Unsuccessful test with relatives url
    def test_match_url_without_http_fail(self):
        browser = self.myBrowser
        res = browser.urlNotRegWithoutHttp.match("http://woob.tech/news")
        self.assertIsNone(res)

    # Checks that build returns the right url when it needs to add
    # the value of a parameter
    def test_build_nominal_case(self):
        res = self.myBrowser.urlValue.build(id=2)
        self.assertEquals(res, "http://test.com/2")

    # Checks that build returns the right url when it needs to add
    # identifiers and values of some parameters
    def test_build_urlParams_OK(self):
        res = self.myBrowser.urlParams.build(id=2, name="woob")
        self.assertEquals(res, "http://test.com/?id=2&name=woob")

    # Checks that build returns the right url when it needs to add
    # identifiers and values of some parameters.
    # The same parameters can be in multiple patterns.
    def test_build_urlSameParams_OK(self):
        res = self.myBrowser.urlSameParams.build(id=2, name="woob")
        self.assertEquals(res, "http://test.com?id=2&name=woob")

    # Checks that an exception is raised when a parameter is missing
    # (here, the parameter name)
    def test_build_urlParams_KO_missedparams(self):
        self.assertRaises(UrlNotResolvable, self.myBrowser.urlParams.build,
                          id=2)

    # Checks that an exception is raised when there is an extra parameter
    # added to the build function (here, the parameter title)
    def test_build_urlParams_KO_moreparams(self):
        self.assertRaises(UrlNotResolvable, self.myBrowser.urlParams.build,
                          id=2, name="woob", title="test")

    # Check that an assert is sent if both klass is none
    def test_ishere_klass_none(self):
        self.assertRaisesRegexp(AssertionError, "You can use this method" +
                                " only if there is a Page class handler.",
                                self.myBrowser.urlRegex.is_here, id=2)

    def test_custom_baseurl(self):
        class MyBrowser(PagesBrowser):
            BASEURL = 'https://example.org/1/'
            CUSTOM_BASEURL = 'https://example.org/2/'

            my_url = URL(r'mypath')
            my_other_url = URL(r'mypath', base='CUSTOM_BASEURL')

        browser = MyBrowser()
        assert browser.my_url.build() == 'https://example.org/1/mypath'
        assert browser.my_other_url.build() == 'https://example.org/2/mypath'

        assert browser.my_url.match('https://example.org/1/mypath')
        assert not browser.my_url.match('https://example.org/2/mypath')
        assert browser.my_other_url.match('https://example.org/2/mypath')
        assert not browser.my_other_url.match('https://example.org/1/mypath')

    def test_with_page(self):
        """Test getting an URL with another page class."""
        class MyPage(Page):
            pass

        class MyOtherPage(Page):
            pass

        url = URL(r'mypath', r'myotherpath', MyPage)
        other_url = url.with_page(MyOtherPage)

        assert isinstance(other_url, URL)
        assert url is not other_url
        assert url.urls == other_url.urls
        assert url.klass is MyPage
        assert other_url.klass is MyOtherPage
        assert url.browser is other_url.browser

    def test_with_page_for_browser(self):
        """Test getting an URL with another page class."""
        class MyPage(Page):
            pass

        class MyOtherPage(Page):
            pass

        class MyBrowser(PagesBrowser):
            my_url = URL(r'mypath', MyPage)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

                # We copy the original URL as a list so that it doesn't
                # get integrated in the browser's URL collection.
                self.original = [self.my_url]

                self.my_url = self.my_url.with_page(MyOtherPage)

        browser = MyBrowser()
        original_url = browser.original[0]
        url = browser.my_url

        assert isinstance(url, URL)
        assert url is not original_url
        assert url.urls == original_url.urls
        assert original_url.klass is MyPage
        assert url.klass is MyOtherPage
        assert dict(browser._urls) == {'my_url': url}
        assert original_url.browser is None
        assert url.browser is browser

    def test_with_page_browser_url(self):
        """Test getting a BrowserParamURL with another page class."""
        class MyPage(Page):
            pass

        class MyOtherPage(Page):
            pass

        url = BrowserParamURL(r'mypath', r'myotherpath', MyPage)
        other_url = url.with_page(MyOtherPage)

        assert isinstance(other_url, BrowserParamURL)
        assert url is not other_url
        assert url.urls == other_url.urls
        assert url.klass is MyPage
        assert other_url.klass is MyOtherPage
        assert url.browser is other_url.browser

    # We cannot use the parametrize fixture here because the test class
    # inherits from TestCase, which prevents the use of parametrize with a
    # function taking a 'self' as input.
    def _test_with_urls_with_class(self, url_cls):
        class MyPage(Page):
            pass

        path = ('mypath', 'myotherpath')
        new_path = 'newpath'

        url = url_cls(*path, MyPage)
        url.browser = self.myBrowser
        other_url_additional = url.with_urls(new_path, clear=False)
        other_url_additional_no_match_first = url.with_urls(new_path, clear=False, match_new_first=False)
        other_url_clear = url.with_urls(new_path)

        assert isinstance(other_url_additional, url_cls)
        assert isinstance(other_url_additional_no_match_first, url_cls)
        assert isinstance(other_url_clear, url_cls)

        assert url is not other_url_additional
        assert url is not other_url_additional_no_match_first
        assert url is not other_url_clear
        assert other_url_additional is not other_url_clear

        # old urls are kept with clear=False
        assert all(path in other_url_additional.urls for path in url.urls)
        assert all(path in other_url_additional_no_match_first.urls for path in url.urls)
        # old urls are removed with clear=True
        assert not any(path in other_url_clear.urls for path in url.urls)

        assert url.klass is MyPage
        assert other_url_additional.klass is MyPage
        assert other_url_additional_no_match_first.klass is MyPage
        assert other_url_clear.klass is MyPage

        assert other_url_additional.browser is None
        assert other_url_additional_no_match_first.browser is None
        assert other_url_clear.browser is None

        # New paths are matched first
        assert other_url_additional.urls == ['newpath', 'mypath', 'myotherpath']
        # Old paths are matched first
        assert other_url_additional_no_match_first.urls == ['mypath', 'myotherpath', 'newpath']

        void_url = url.with_urls()
        assert isinstance(void_url, url_cls)
        assert void_url is not url
        assert void_url.klass is MyPage
        assert not void_url.urls

        # Original url must not have been modified
        assert url.urls == ['mypath', 'myotherpath']

    def test_with_urls(self):
        """Test getting an URL with another path list."""
        self._test_with_urls_with_class(URL)

    def test_with_urls_browser_url(self):
        """Test getting an BrowserParamURL with another path list."""
        self._test_with_urls_with_class(BrowserParamURL)


def test_normalize_url():
    tests = [
        ('https://foo/bar/baz', 'https://foo/bar/baz'),

        ('https://FOO/bar', 'https://foo/bar'),

        ('https://foo:1234/bar', 'https://foo:1234/bar'),
        ('https://foo:443/bar', 'https://foo/bar'),
        ('http://foo:1234', 'http://foo:1234'),
        ('http://foo:80', 'http://foo'),
        ('http://User:Password@foo:80', 'http://User:Password@foo'),
        ('http://User:Password@foo:80/bar', 'http://User:Password@foo/bar'),

        ('http://foo#BAR', 'http://foo#BAR'),
        ('https://foo#BAR', 'https://foo#BAR'),
        ('https://foo:443#BAR', 'https://foo#BAR'),
    ]
    for todo, expected in tests:
        assert normalize_url(todo) == expected
