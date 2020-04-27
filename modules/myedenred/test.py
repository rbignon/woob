# -*- coding: utf-8 -*-

# Copyright(C) 2017      Théo Dorée
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals


from weboob.tools.test import BackendTest

from .pages import parseInput

class MyedenredTest(BackendTest):
    MODULE = 'myedenred'

    def test_document(self):
        subscriptions = list(self.backend.iter_subscription())
        assert subscriptions

        for sub in subscriptions:
            docs = list(self.backend.iter_documents(sub))
            assert docs

            for doc in docs:
                content = self.backend.download_document(doc)
                assert content

    def test_parseInput(self):
        input = '''
        {response_type:"code",client_id:a["default"].EDCId,scope:"openid offline_access edg-xp-appcontainer-api edg-xp-wallet-management-api",redirect_uri:f+"/connect",state:d,nonce:123,acr_values:a["default"].acr_values,ui_locales:"fr-fr",code_challenge:n,code_challenge_method:"S256"}
        '''

        result = parseInput(input)

        self.assertEqual(result["code_challenge_method"], "S256")
        self.assertEqual(result["nonce"], "123")
        self.assertEqual(result["response_type"], "code")
        self.assertEqual(result["scope"], "openid offline_access edg-xp-appcontainer-api edg-xp-wallet-management-api")
        self.assertEqual(result["ui_locales"], "fr-fr")
