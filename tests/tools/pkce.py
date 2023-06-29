from base64 import urlsafe_b64encode
from hashlib import sha256

from woob.tools.pkce import PKCEChallengeType, PKCEData


def test_pkce_s256():
    data = PKCEData.build()

    assert data.method == 'S256'

    digest = sha256(data.verifier.encode('ascii')).digest()
    assert data.challenge == urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def test_pkce_plain():
    data = PKCEData.build(PKCEChallengeType.PLAIN)

    assert data.method == 'plain'
    assert data.challenge
    assert data.challenge == data.verifier
