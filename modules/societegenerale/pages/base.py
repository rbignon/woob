# Copyright(C) 2010-2011 Jocelyn Jaubert
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

from decimal import Decimal

from woob.browser.filters.standard import CleanText
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class BasePage(HTMLPage):
    def on_load(self):
        if self.doc.xpath('//script[contains(text(), "gdpr/recueil")]'):
            self.browser.open(
                "https://particuliers.secure.societegenerale.fr/icd/gdpr/data/gdpr-update-compteur-clicks-client.json"
            )

    def get_error(self):
        try:
            return self.doc.xpath('//span[@class="error_msg"]')[0].text.strip()
        except IndexError:
            return None

    def parse_decimal(self, td):
        value = CleanText(".")(td)
        if value:
            return Decimal(FrenchTransaction.clean_amount(value))
        else:
            return NotAvailable
