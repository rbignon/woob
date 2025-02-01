# Copyright(C) 2012 Romain Bignon
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
from woob.tools.value import Value


class PrixCarburantsTest(BackendTest):
    MODULE = "prixcarburants"

    def setUp(self):
        if not self.is_backend_configured():
            self.backend.config["Zipcode"] = Value(value="59000")

    def test_search_products(self):
        products = list(self.backend.search_products("gpl"))
        self.assertTrue(len(products) == 1)

    def test_prixcarburants(self):
        products = list(self.backend.search_products("gpl"))
        product = products[0]
        product.backend = self.backend.name
        prices = list(itertools.islice(self.backend.iter_prices([product]), 0, 20))
        self.assertGreater(len(prices), 0)
        self.backend.fillobj(prices[0])
