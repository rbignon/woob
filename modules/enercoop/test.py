# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
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


class EnercoopTest(BackendTest):
    MODULE = 'enercoop'

    def test_subs(self):
        subs = list(self.backend.iter_subscription())
        assert subs
        sub = subs[0]
        assert subs[0].id
        assert subs[0].label

        docs = list(self.backend.iter_documents(sub))
        assert docs

        doc = docs[0]
        assert doc.id
        assert doc.label
        assert doc.total_price
        assert doc.url
