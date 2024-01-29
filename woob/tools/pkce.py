# Copyright(C) 2023 Powens
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

"""Utilities for handling PKCE (RFC 7636)."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from enum import Enum
from hashlib import sha256
from os import urandom
from typing import NamedTuple

__all__ = [
    'PKCEChallengeType',
    'PKCEData',
]


class PKCEChallengeType(str, Enum):
    """PKCE challenge type."""

    PLAIN = ('PLAIN')
    """Plaintext challenge."""

    S256 = ('S256')
    """SHA-256 challenge."""


class PKCEData(NamedTuple):
    """PKCE data to generate."""

    verifier: str
    """The verifier to transmit at token call."""

    challenge: str
    """The challenge to transmit in the authorization URL."""

    method: str
    """The method to transmit in the authorization URL."""

    @classmethod
    def build(
        cls: type[PKCEData],
        type_: PKCEChallengeType = PKCEChallengeType.S256,
    ) -> PKCEData:
        r"""Build random data for OAuth2 PKCE extension.

        :param type\_: The type of challenge to produce.
        :return: The PKCE data.
        """
        # While RFC 7636 section 4.1 allows verifiers to use the whole uppercase and
        # lowercase latin alphabet, some APIs restrict the verifier charset to hex
        # characters (0-9, a-f), hence the limitation employed here.
        #
        # RFC 7636 section 7.1 mandates 256 bits of entropy (32 8-bit bytes), and
        # section 4.1 mandates between 43 and 128 characters in length; this method
        # makes us generate 64 characters with enough entropy, we're in the clear!
        verifier = urandom(32).hex()

        if type_ == PKCEChallengeType.S256:
            digest = sha256(verifier.encode('ascii')).digest()
            challenge = urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
            return cls(verifier=verifier, method='S256', challenge=challenge)

        if type_ == PKCEChallengeType.PLAIN:
            return cls(verifier=verifier, method='plain', challenge=verifier)

        raise ValueError(f'Unsupported PKCE challenge type "{type_}"')
