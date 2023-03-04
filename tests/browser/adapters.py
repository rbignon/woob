from unittest import TestCase

import requests

from woob.browser import Browser
from woob.browser.adapters import LowSecHTTPAdapter


class TestAdapter(TestCase):
    def test_ciphers(self):
        # Test there is an exception without ciphers supplied.
        browser = Browser()
        self.assertRaises(requests.exceptions.SSLError, browser.open, 'https://dh1024.badssl.com/')

        # Test a browser with more permissive ciphers.
        class PermissiveBrowser(Browser):
            HTTP_ADAPTER_CLASS = LowSecHTTPAdapter

        permissive_browser = PermissiveBrowser()
        r = permissive_browser.open('https://dh1024.badssl.com/')
        self.assertEqual(r.status_code, 200)

        # No side effects.
        r = permissive_browser.open('http://example.org')
        self.assertEqual(r.status_code, 200)

        # change of ciphers is contextual, does not affect previous browser.
        self.assertRaises(requests.exceptions.SSLError, browser.open, 'https://dh1024.badssl.com/')
