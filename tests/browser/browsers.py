import sys
import ssl
import pytest

import requests

from woob.browser import Browser


@pytest.fixture(scope="function")
def badssl_self_signed_bundle_path(tmp_path_factory):
    bundle_path = tmp_path_factory.mktemp('ca_bundle') / 'selfsignedbundle.pem'

    # Get the self-signed.badssl.com certificate and store it to be used in
    # verify/VERIFY parameters.
    with open(bundle_path, 'w', encoding='utf-8') as fp:
        if sys.version_info >= (3, 10):
            pem_cert = ssl.get_server_certificate(('self-signed.badssl.com', 443))
        else:
            # On older versions of Python, ssl.get_server_certificate()
            # doesn't support SNI.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            with ssl.create_connection(('self-signed.badssl.com', 443)) as sock:
                with context.wrap_socket(sock, server_hostname='self-signed.badssl.com') as sslsock:
                    der_cert = sslsock.getpeercert(True)
                    pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)

        fp.write(pem_cert)

    return bundle_path


class TestBrowser:
    def test_verify(self, badssl_self_signed_bundle_path):
        class NoRetryBrowser(Browser):
            MAX_RETRIES = 0  # don't want to retry when we got a SSL error

        # Browser with static VERIFY attribute
        class BrowserVerifyTrue(NoRetryBrowser):
            VERIFY = True

        class BrowserVerifyFalse(NoRetryBrowser):
            VERIFY = False

        class BrowserVerifyPath(NoRetryBrowser):
            VERIFY = badssl_self_signed_bundle_path

        # Tests which fail
        with pytest.raises(requests.exceptions.SSLError):
            BrowserVerifyTrue().open('https://self-signed.badssl.com/')

        with pytest.raises(requests.exceptions.SSLError):
            BrowserVerifyFalse().open('https://self-signed.badssl.com/', verify=True)

        # Tests which succeed
        r = BrowserVerifyTrue(verify=False).open('https://self-signed.badssl.com/')
        assert r.status_code == 200

        r = BrowserVerifyTrue().open('https://self-signed.badssl.com/', verify=False)
        assert r.status_code == 200

        r = BrowserVerifyTrue().open('https://self-signed.badssl.com/', verify=badssl_self_signed_bundle_path)
        assert r.status_code == 200

        r = BrowserVerifyFalse().open('https://self-signed.badssl.com/')
        assert r.status_code == 200

        r = BrowserVerifyPath().open('https://self-signed.badssl.com/')
        assert r.status_code == 200
