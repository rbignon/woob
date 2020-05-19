# -*- coding: utf-8 -*-

# Copyright(C) 2020 Budget Insight
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

# flake8: compatible

from __future__ import unicode_literals

from weboob.browser.pages import HTMLPage, LoggedPage, pagination
from weboob.browser.elements import ListElement, ItemElement, method
from weboob.browser.filters.standard import (
    CleanText, CleanDecimal, Regexp, Date, Currency as CleanCurrency,
    MapIn, Map, Field,
)
from weboob.browser.filters.html import AbsoluteLink
from weboob.capabilities.bank import (
    Transfer, TransferStatus, TransferFrequency,
)
from weboob.tools.date import parse_french_date
from weboob.tools.compat import urljoin


class TransferListPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_transfers(ListElement):
        item_xpath = '//a[has-class("ticket")]'

        def next_page(self):
            part = CleanText('//div/@data-brs-infinite-scroll-trigger')(self)
            if not part:
                return
            return urljoin(self.page.url, part)

        class item(ItemElement):
            klass = Transfer

            obj_url = AbsoluteLink('.')

            obj_exec_date = Date(
                CleanText('.//div[has-class("ticket__date")]'),
                parse_func=parse_french_date,
                strict=False,  # these smartasses hide the year when it's current year
            )
            obj_label = CleanText('.//div[has-class("ticket__title")]')

            _bank_iban = CleanText('.//div[has-class("ticket__body-content")]')
            obj_recipient_iban = CleanText(
                # format: "{bank name} • {iban with spaces}"
                # or just "{iban with spaces}"
                Regexp(_bank_iban, r'^(?:.*• )?([A-Z0-9 ]+?)$'),
                symbols=' ',
            )
            obj_recipient_label = CleanText('.//div[has-class("ticket__body-title")]')

            STATUSES = {
                'Terminé': TransferStatus.DONE,
                'En attente': TransferStatus.SCHEDULED,
                'Non Réalisé': TransferStatus.CANCELLED,
                # TODO what's the label for bank_canceled
            }
            _status_text = CleanText('.//div[has-class("ticket__foot-status")]')
            obj_status = MapIn(_status_text, STATUSES)

            def obj__is_instant(self):
                status = Field('status')(self)
                # hardcoded embedded svg. no filename, no class, no id.
                return (
                    status == TransferStatus.DONE
                    and self.el.xpath('.//div[has-class("ticket__foot-icon")]/svg')
                )

            # warning: sometimes the amount is positive, sometimes negative
            obj_amount = CleanDecimal.French('.//div[has-class("ticket__foot-value")]', sign='+')

            obj_currency = CleanCurrency('.//div[has-class("ticket__foot-value")]')


FILLING_XPATH = '//th[normalize-space(text())="%s"]/following-sibling::td'


class TransferInfoPage(LoggedPage, HTMLPage):
    @method
    class fill_transfer(ItemElement):
        obj_label = CleanText(FILLING_XPATH % 'Libellé')
        obj_id = CleanText(FILLING_XPATH % 'Référence')

    @method
    class fill_periodic_transfer(ItemElement):
        FREQ_LABELS = {
            'Hebdomadaire': TransferFrequency.WEEKLY,
            'Mensuelle': TransferFrequency.MONTHLY,
            'Trimestrielle': TransferFrequency.QUARTERLY,
            'Semestrielle': TransferFrequency.BIANNUAL,
            'Annuelle': TransferFrequency.YEARLY,
        }

        obj_frequency = Map(CleanText(FILLING_XPATH % 'Périodicité'), FREQ_LABELS)

        obj_first_due_date = Date(CleanText(FILLING_XPATH % 'à partir du'), dayfirst=True)
        # on this site, a periodic transfer may be forever (no end date)
        obj_last_due_date = Date(CleanText(FILLING_XPATH % "jusqu'au"), dayfirst=True, default=None)
