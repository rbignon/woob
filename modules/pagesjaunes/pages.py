# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent A
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

import re
from datetime import time

from dateutil import rrule

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import AbsoluteLink, HasElement, XPath
from woob.browser.filters.standard import BrowserURL, CleanText, Env, Field, Regexp
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.contact import OpeningRule, Place


class ResultsPage(HTMLPage):
    @pagination
    @method
    class iter_contacts(ListElement):
        item_xpath = '//section[@id="listResults"]/ul/li'

        def next_page(self):
            if XPath('//div/@class="pagination"', default=False)(self):
                next_page = int(Env('page')(self)) + 1
                return BrowserURL('search',
                                  city=Env('city'),
                                  pattern=Env('pattern'),
                                  page=next_page)(self)

        class item(ItemElement):
            klass = Place

            obj_name = CleanText('.//a[has-class("denomination-links")]')
            obj_address = CleanText('.//a[has-class("adresse")]')

            def obj_phone(self):
                tel = []
                for _ in XPath(
                        './/div[has-class("tel-zone")][span[contains(text(),"Tél")]]//strong[@class="num"]')(self):
                    tel.append(Regexp(CleanText('.', replace=[(' ', '')]), r'^0(\d{9})$', r'+33\1')(_))

                return " / ".join(tel)

            def obj_url(self):
                if CleanText('.//a[has-class("denomination-links")]/@href', replace=[('#', '')])(self):
                    return AbsoluteLink('.//a[has-class("denomination-links")]')(self)
                return NotAvailable

            obj_opening = HasElement('.//span[text()="Horaires"]', NotLoaded, NotAvailable)


class PlacePage(HTMLPage):
    @method
    class iter_hours(ListElement):
        item_xpath = '//div[@id="infos-horaires"]/ul/li[@class="horaire-ouvert"]'

        class item(ItemElement):
            klass = OpeningRule

            def obj_dates(self):
                wday = CleanText('./p')(self)
                wday = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'].index(wday.lower())
                assert wday >= 0
                return rrule.rrule(rrule.DAILY, byweekday=wday, count=1)

            def obj_times(self):
                times = []
                for sub in XPath('.//li')(self):
                    t = CleanText('.')(sub)
                    m = re.match(r'(\d{2})h(\d{2}) - (\d{2})h(\d{2})$', t)
                    if m:
                        m = [int(x) for x in m.groups()]
                        times.append((time(m[0], m[1]), time(m[2], m[3])))
                return times

            def obj_is_open(self):
                return len(Field('times')(self)) > 0
