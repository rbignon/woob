# -*- coding: utf-8 -*-

# Copyright(C) 2016      Phyks
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


from datetime import datetime, timedelta

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Link
from woob.browser.filters.standard import CleanDecimal, CleanText, DateTime, Env, Eval, Format
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.calendar import CATEGORIES, TICKET

from .calendar import CentQuatreEvent


class CentQuatrePage(HTMLPage):
    @property
    def logged(self):
        return bool(self.doc.xpath(u'//*[@id="account_logout"]'))


class LoginPage(CentQuatrePage):
    def login(self, email, password):
        form = self.get_form(id='login_form')
        form['login'] = email
        form['password'] = password
        form.submit()

class TicketsPage(CentQuatrePage, LoggedPage):
    def list_tickets(self, date_from=None, date_to=None):
        tickets_containers = self.doc.xpath(u'//*[@class="product_container"]')
        tickets = []
        for ticket_container in tickets_containers:
            date = datetime.strptime(
                ticket_container.xpath(u'//*[@class="day"]')[0].text.strip(),
                u'%A, %d %B %Y - %H:%M'
            )
            if date_from and date < date_from:
                continue
            if date_to and date > date_to:
                continue
            tickets.append(
                ticket_container.xpath(
                    u'//*[@class="file_number"]/a'
                )[0].text.strip().split(' ')[1]
            )
        return tickets


class TicketsDetailsPage(CentQuatrePage, LoggedPage):
    @method
    class get_event_details(ListElement):
        item_xpath = u'//*[@class="product_container"]'

        class EventDetails(ItemElement):
            klass = CentQuatreEvent

            obj_id = Env('fileId')
            obj_start_date = DateTime(
                CleanText(u'//*[@class="date"]')
            )
            obj_end_date = Eval(
                lambda x: x + timedelta(hours=1),
                obj_start_date
            )
            obj_timezone = u'Europe/Paris'
            obj_summary = CleanText(
                u'//*[@class="content_product_info"]//*[contains(@class, "title")]'
            )
            obj_city = u'Paris'
            obj_location = Format(
                "%s, %s",
                CleanText(
                    u'(//*[@class="location"])[1]'
                ),
                CleanText(
                    u'//*[@class="address"]'
                )
            )
            obj_category = CATEGORIES.SPECTACLE
            obj_price = CleanDecimal(
                CleanText(
                    u'(//*[@class="unit_price with_beneficiary"])[1]'
                )
            )
            obj_description = Format(
                u'%s. %s. %.2f€.',
                CleanText(
                    u'(//*[contains(@class, "tariff") and contains(@class, "with_beneficiary")])[1]'
                ),
                CleanText(
                    u'(//*[contains(@class, "seat") and contains(@class, "with_beneficiary")])[1]'
                ),
                obj_price,
            )
            obj_ticket = TICKET.AVAILABLE
            def obj_url(self):
                return (
                    u'%s%s' % (
                        self.page.browser.BASEURL,
                        Link(
                            u'//*[@class="alternative_button mticket"]/a'
                        )(self)
                    )
                )
