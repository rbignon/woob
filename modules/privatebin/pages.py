# -*- coding: utf-8 -*-

# Copyright(C) 2021      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

import datetime
from base64 import b64decode, b64encode
from os import urandom
from zlib import DEFLATED, MAX_WBITS, compressobj, decompress

try:
    from Cryptodome.Cipher import AES
    from Cryptodome.Hash import HMAC, SHA256
    from Cryptodome.Protocol.KDF import PBKDF2
except ImportError:
    from Crypto.Cipher import AES
    from Crypto.Hash import HMAC, SHA256
    from Crypto.Protocol.KDF import PBKDF2
# privatebin uses base64 AND base58... why on earth are they so inconsistent?
from base58 import b58decode, b58encode

from woob.browser.pages import JsonPage
from woob.tools.json import json


class ReadPage(JsonPage):
    def decode_paste(self, textkey):
        return decrypt(textkey, self.doc)

    def get_expire(self):
        ts = self.doc['meta']["created"] + self.doc['meta']["time_to_live"]
        return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)

    def has_paste(self):
        return "id" in self.doc


def fix_base64(s):
    pad = {
        2: '==',
        3: '=',
    }
    return s + pad.get(len(s) % 4, '')


class WritePage(JsonPage):
    AGES = {
        300: '5min',
        600: '10min',
        3600: '1hour',
        86400: '1day',
        7 * 86400: '1week',
        30 * 86400: '1month',
        30.5 * 86400: '1month',  # pastoob's definition of "1 month" is approximately okay
        365 * 86400: '1year',
        None: 'never',
        0: 0,
    }

    def fill_paste(self, obj):
        obj._serverid = self.doc["id"]
        obj._deletetoken = self.doc["deletetoken"]


def hash_func(k, s):
    return HMAC.new(k, s, SHA256).digest()


def decrypt(textkey, params):
    # their json format is rather poor https://github.com/PrivateBin/PrivateBin/wiki/API
    # also need to read several .jsonld in https://github.com/PrivateBin/PrivateBin/tree/master/js
    iv64, salt64, iterations, keylen, taglen, algoname, modename, comprname = params["adata"][0]

    iv = b64decode(iv64)
    salt = b64decode(salt64)
    taglen //= 8
    keylen //= 8

    # not base64, but base58, just because.
    key = derive_key(b58decode(textkey), salt, keylen, iterations)

    data = b64decode(params['ct'])
    ciphertext = data[:-taglen]
    tag = data[-taglen:]

    # iv = trunc_iv(iv, ciphertext, taglen)

    mode_str = params["adata"][0][6]
    assert mode_str == "gcm"
    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)

    header = build_header(params["adata"])
    cipher.update(header)

    decrypted = cipher.decrypt_and_verify(ciphertext, tag)
    # there's no zlib header
    # one more json layer, yeah...
    finaldict = json.loads(decompress(decrypted, wbits=-8))

    return finaldict["paste"]


def derive_key(binkey, salt, keylen, iterations):
    return PBKDF2(binkey, dkLen=keylen, salt=salt, count=iterations, prf=hash_func)


def build_header(adata):
    return json.dumps(adata, separators=(",", ":")).encode("ascii")


def encrypt(plaintext, expire_string="1week", burn_after_reading=False, discussion=False):
    burn_after_reading = int(burn_after_reading)
    discussion = int(discussion)

    plaintext = json.dumps({"paste": plaintext})
    compressor = compressobj(-1, DEFLATED, -MAX_WBITS)
    contents = compressor.compress(plaintext.encode('utf-8'))
    contents += compressor.flush()

    iv = urandom(16)
    salt = urandom(8)
    iterations = 100000
    keylen_bits = 256
    taglen_bits = 128

    url_bin_key = urandom(32)
    key = derive_key(url_bin_key, salt, keylen_bits // 8, iterations)

    # smalliv = trunc_iv(iv, plaintext, 0)

    cipher = AES.new(key, AES.MODE_GCM, nonce=iv, mac_len=taglen_bits // 8)

    adata = [
        [
            b64encode(iv).decode("ascii"),
            b64encode(salt).decode("ascii"),
            iterations,
            keylen_bits,
            taglen_bits,
            "aes",
            "gcm",
            "zlib",
        ],
        "plaintext",
        discussion,
        burn_after_reading,
    ]

    cipher.update(build_header(adata))
    ciphertext = b''.join(cipher.encrypt_and_digest(contents))

    return (
        {
            "adata": adata,
            "v": 2,
            "ct": b64encode(ciphertext).decode("ascii"),
            "meta": {
                "expire": expire_string,
            },
        }, b58encode(url_bin_key).decode("ascii"),
    )
