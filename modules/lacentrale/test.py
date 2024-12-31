# -*- coding: utf-8 -*-

# Copyright(C) 2014 Vicnet
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


import itertools

from woob.tools.test import BackendTest


class LaCentraleTest(BackendTest):
    MODULE = 'lacentrale'

    def test_lacentrale(self):
        products = list(itertools.islice(self.backend.search_products(u'10000€,pro'), 0, 20))
        self.assertTrue(len(products) > 0)
        product = products[0]
        product.backend = self.backend.name
        prices = list(itertools.islice(self.backend.iter_prices([product]), 0, 20))
        self.assertTrue(len(prices) > 0)
