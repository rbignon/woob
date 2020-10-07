# -*- coding: utf-8 -*-

# Copyright(C) 2018      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from datetime import time
import re

from dateutil import rrule
from weboob.browser.elements import method, ListElement, ItemElement
from weboob.browser.filters.standard import CleanText, Regexp, Field, Env, BrowserURL
from weboob.browser.filters.html import AbsoluteLink, HasElement, XPath
from weboob.browser.pages import HTMLPage, pagination
from weboob.capabilities.base import NotLoaded, NotAvailable
from weboob.capabilities.contact import Place, OpeningRule


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
