# -*- coding: utf-8 -*-

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

from woob.browser import URL, PagesBrowser
from woob.capabilities.base import UserError

from .pages import ComparisonResultsPage, IndexPage, ShopInfoPage


__all__ = ["PrixCarburantsBrowser"]


class PrixCarburantsBrowser(PagesBrowser):
    BASEURL = "https://www.prix-carburants.gouv.fr"
    TOKEN = None

    result_page = URL("/recherche/", ComparisonResultsPage)
    shop_page = URL(r"/itineraire/infos/(?P<_id>\d+)", ShopInfoPage)
    index_page = URL("/$", IndexPage)

    def iter_products(self):
        return self.index_page.go().iter_products()

    def get_token(self):
        self.TOKEN = self.index_page.stay_or_go().get_token()

    def iter_prices(self, zipcode, town, product):
        if self.TOKEN is None:
            self.get_token()

        data = {
            "rechercher[localisation]": "%s" % zipcode or town,
            "rechercher[choix_carbu][]": "%s" % product.id,
            "rechercher[_token]": "%s" % self.TOKEN,
            "rechercher[geolocalisation_long]": "",
            "rechercher[geolocalisation_lat]": "",
            "rechercher[departement]": "",
            "rechercher[type_enseigne]": "",
        }

        # self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        self.index_page.go(data=data)

        if not self.result_page.is_here():
            raise UserError("Bad zip or product")

        if not product.name:
            product.name = self.page.get_product_name(product.id)

        return self.page.iter_results(product=product)

    def get_shop_info(self, id):
        self.session.headers.update({"X-Requested-With": "XMLHttpRequest"})
        return self.shop_page.go(_id=id).get_info()
