# Copyright(C) 2023 POWENS
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

# flake8: compatible

from base64 import b64encode
from hashlib import sha256
from requests import PreparedRequest

from unittest import TestCase
from woob.browser.browsers import DigestMixin, OAuth2Mixin, PagesBrowser


class FakeStetBrowser(DigestMixin, OAuth2Mixin, PagesBrowser):
    BASEURL = 'http://woob.tech/'


class TestDigestMixin(TestCase):
    """Test DigestMixin behaviour.

    For all the test cases, HTTP_DIGEST_EXCLUDE and HTTP_DIGEST_INCLUDE should
    be removed from the headers once the request is prepared.
    """

    EXPECTED_DIGEST = 'SHA-256=' + b64encode(sha256(b'{"foo": 1, "bar": 2}').digest()).decode()
    EXPECTED_COMPACT_DIGEST = 'SHA-256=' + b64encode(sha256(b'{"foo":1,"bar":2}').digest()).decode()

    class FakeRequest:
        url = 'http://woob.tech/'
        method = 'POST'
        body =  b'{"foo": 1, "bar": 2}'
        data = b'{"foo": 1, "bar": 2}'
        auth = None
        cookies = None
        files = None
        json = None
        params = None
        hooks = None
        headers = {}

    def setUp(self):
        self.myBrowser = FakeStetBrowser()
        self.req = self.FakeRequest()

    def execute_assertions(self, preq: PreparedRequest, expected_digest: str) -> None:
        assertions = [
            ('Digest', expected_digest),
            ('HTTP_DIGEST_EXCLUDE', None),
            ('HTTP_DIGEST_INCLUDE', None),
        ]

        for assertion in assertions:
            self.assertEqual(preq.headers.get(assertion[0], None), assertion[1])

    def test_http_digest_method(self):
        """It should add a digest for all methods if HTTP_DIGEST_METHODS not overridden."""

        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=self.EXPECTED_DIGEST)

    def test_http_digest_method_default(self):
        """It should add a digest for all methods if HTTP_DIGEST_METHODS is none."""

        self.myBrowser.HTTP_DIGEST_METHODS = None
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=self.EXPECTED_DIGEST)

    def test_http_digest_method_post(self):
        """It should add a digest if the request method is in HTTP_DIGEST_METHODS."""

        self.myBrowser.HTTP_DIGEST_METHODS = ('POST',)
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=self.EXPECTED_DIGEST)

    def test_http_digest_method_get(self):
        """It should not add a digest if the request method is not in HTTP_DIGEST_METHODS."""

        self.myBrowser.HTTP_DIGEST_METHODS = ('GET',)
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=None)

    def test_http_digest_method_empty_list(self):
        """It should not add a digest if HTTP_DIGEST_METHODS is an empty list."""

        self.myBrowser.HTTP_DIGEST_METHODS = ()
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=None)

    def test_include_header(self):
        """It should add a digest if HTTP_DIGEST_INCLUDE is in request headers.

        HTTP_DIGEST_INCLUDE takes precedence over HTTP_DIGEST_METHODS.
        """

        self.myBrowser.HTTP_DIGEST_METHODS = ()
        self.req.headers = {'HTTP_DIGEST_INCLUDE': 'true'}
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=self.EXPECTED_DIGEST)

    def test_exclude_header(self):
        """It should add a digest if HTTP_DIGEST_EXCLUDE is in request header.

        HTTP_DIGEST_EXCLUDE takes precedence over HTTP_DIGEST_METHODS.
        """

        self.myBrowser.HTTP_DIGEST_METHODS = None
        self.req.headers = {'HTTP_DIGEST_EXCLUDE': 'true'}
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=None)

    def test_compact_digest(self):
        """It should add a compact digest if HTTP_DIGEST_COMPACT_JSON is true."""

        self.myBrowser.HTTP_DIGEST_COMPACT_JSON = True
        self.req.headers = {'Content-Type': 'application/json'}
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=self.EXPECTED_COMPACT_DIGEST)

    def test_compact_digest_empty_list(self):
        """It should not add a compact digest if HTTP_DIGEST_METHODS is an empty set."""

        self.myBrowser.HTTP_DIGEST_METHODS = ()
        self.myBrowser.HTTP_DIGEST_COMPACT_JSON = True
        self.req.headers = {'Content-Type': 'application/json'}
        preq = self.myBrowser.prepare_request(self.req)

        self.execute_assertions(preq, expected_digest=None)
