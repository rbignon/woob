# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from base64 import b64encode
from collections import OrderedDict
from io import BytesIO

from weboob.capabilities.captcha import UnsolvableCaptcha, InvalidCaptcha
from weboob.browser import DomainBrowser
from weboob.tools.compat import parse_qsl
from weboob.tools.json import json


def parse_qs(d):
    return dict(parse_qsl(d))


class DeathbycaptchaBrowser(DomainBrowser):
    BASEURL = 'http://api.dbcapi.me'

    def __init__(self, username, password, *args, **kwargs):
        super(DeathbycaptchaBrowser, self).__init__(*args, **kwargs)
        self.username = username
        self.password = password

    def check_correct(self, reply):
        if reply.get('is_correct', '1') == '0':
            raise UnsolvableCaptcha()
        if reply.get('status', '0') == '255':
            raise InvalidCaptcha(reply.get('error', ''))

    def create_job(self, data):
        data64 = b'base64:%s' % b64encode(data)
        files = {
            'captchafile': ('captcha.jpg', BytesIO(data64)),
        }

        post = OrderedDict([
            ('username', self.username),
            ('password', self.password),
        ])

        r = self.open('/api/captcha', data=post, files=files)
        reply = parse_qs(r.text)
        self.check_correct(reply)

        return reply['captcha']

    def create_nocaptcha_job(self, url, key):

        token_params = {
          'googlekey': key,
          'pageurl': url,
        }

        data = OrderedDict([
            ('username', self.username),
            ('password', self.password),
            ('type', 4),
            ('token_params', json.dumps(token_params)),
        ])

        r = self.open('/api/captcha', data=data)
        reply = parse_qs(r.text)
        self.check_correct(reply)

        return reply['captcha']

    def poll(self, id):
        r = self.open('/api/captcha/%s' % id)
        reply = parse_qs(r.text)
        self.check_correct(reply)

        return reply.get('text', None) or None
