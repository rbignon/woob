# -*- coding: utf-8 -*-

# Copyright(C) 2019      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from woob.tools.test import BackendTest


class PrimonialreimTest(BackendTest):
    MODULE = 'primonialreim'

    def test_accounts(self):
        accounts = list(self.backend.iter_accounts())
        assert accounts
        for account in accounts:
            assert account.id
            assert account.label
            assert account.balance
            assert account.type

    def test_documents(self):
        sub, = self.backend.iter_subscription()
        docs = list(self.backend.iter_documents())
        assert docs
        for doc in docs:
            assert doc.id
            assert doc.label
            assert doc.date
            assert doc.type
        assert self.backend.download_document(docs[0])
