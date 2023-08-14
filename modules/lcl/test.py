# Copyright(C) 2023      Gilles Dartiguelongue
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

from woob.capabilities.bill import Document
from woob.tools.test import BackendTest


class LclTest(BackendTest):
    MODULE = "lcl"

    # Bank

    def test_lcl(self):
        accounts = list(self.backend.iter_accounts())
        self.assertGreater(len(accounts), 0)

        account = accounts.pop()
        list(self.backend.iter_coming(account))
        list(self.backend.iter_history(account))

    # Bills

    def test_lcl_get_document(self):
        subscription = next(self.backend.iter_subscription())
        document = next(self.backend.iter_documents(subscription))
        self.assertIsInstance(document, Document)

        document_get = self.backend.get_document(document.id)
        self.assertEqual(document, document_get)

    def test_lcl_get_document_id_normalization(self):
        subscription = next(self.backend.iter_subscription())
        documents = list(self.backend.iter_documents(subscription))

        self.assertTrue(
            all(document.id.startswith(subscription.id) for document in documents)
        )

    def test_lcl_subscription_id(self):
        """Subscription ID must not contain whitespaces.

        Avoid interpretation problems in shell.
        """
        subscription = next(self.backend.iter_subscription())
        self.assertNotIn(" ", subscription.id)
