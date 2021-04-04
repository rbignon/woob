# -*- coding: utf-8 -*-

# Copyright(C) 2014      Oleg Plakhotniuk
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

from woob.tools.test import BackendTest
from itertools import chain


class CitibankTest(BackendTest):
    MODULE = 'citibank'

    def test_history(self):
        """
        Test that there's at least one transaction in the whole history.
        """
        b = self.backend
        ts = chain(*[b.iter_history(a) for a in b.iter_accounts()])
        t = next(ts, None)
        self.assertNotEqual(t, None)
