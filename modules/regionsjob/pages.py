# -*- coding: utf-8 -*-

# Copyright(C) 2014      Bezleputh
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
from datetime import date, timedelta

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import CleanHTML
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanText, Date, Env, Join, Regexp
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities import NotAvailable
from woob.capabilities.job import BaseJobAdvert
from woob.exceptions import ParseError


class LocationPage(JsonPage):
    def get_location(self):
        return Dict("0/value", default="")(self.doc)


class SearchPage(HTMLPage):
    @pagination
    @method
    class iter_job_adverts(ListElement):
        item_xpath = '//div[@class="offer--content"]'

        def next_page(self):
            p = re.match(r"https:\/\/www(.+)\&p=(\d+)\&mode=pagination(.*)", self.page.url)
            if p is not None:
                return f"https://www{p.group(1)}&p={int(p.group(2))+1}&mode=pagination{p.group(3)}"
            else:
                return self.page.url + "&p=2&mode=pagination"

        class item(ItemElement):
            klass = BaseJobAdvert

            def condition(self):
                return Regexp(CleanText("./div/h3/a/@href"), r"/emplois/(.*)\.html", default=None)(self)

            def obj_id(self):
                site = Regexp(CleanText("./div/h3/a/@href"), r"https://www\.(.*)\.com", default=None)(self)
                if site is None:
                    site = Regexp(Env("domain"), r"https://www\.(.*)\.com")(self)

                _id = Regexp(CleanText("./div/h3/a/@href"), r"/emplois/(.*)\.html")(self)
                return "%s#%s" % (site, _id)

            obj_url = CleanText("./div/h3/a/@href")
            obj_title = CleanText("./div/h3/a/@title")
            obj_society_name = CleanText('./div/span[@class="entname"]')
            obj_place = CleanText('./div/div/span[@class="loc "]/span')
            obj_contract_type = CleanText('./div/div/span[@class="contract"]/span')

            def obj_publication_date(self):
                _date = CleanText('./div/div/span[@class="time"]')
                try:
                    return Date(_date)(self)
                except ParseError:
                    str_date = _date(self)
                    if "hier" in str_date:
                        return date.today() - timedelta(days=1)
                    else:
                        return date.today()


class AdvertPage(HTMLPage):
    @method
    class get_job_advert(ItemElement):
        klass = BaseJobAdvert

        obj_description = CleanText(Join("\n", '//section[@class="content modal"]', textCleaner=CleanHTML))
        obj_id = Env("_id")
        obj_url = BrowserURL("advert_page", _id=Env("_id"))
        obj_publication_date = Date(
            Regexp(CleanText('//span[@class="retrait"]/span'), r"(\d{2}/\d{2}/\d{4})", default=NotAvailable),
            default=NotAvailable,
        )
        obj_title = CleanText("//h1/span")
        obj_society_name = CleanText('//a[@id="link-company"]')

        obj_contract_type = CleanText('//li/span[text() = "Type de contrat : "]/following-sibling::span[1]')
        obj_place = CleanText('//li/span[text() = "Localité : "]/following-sibling::span[1]')
        obj_pay = CleanText('//li/span[text() = "Salaire : "]/following-sibling::span[1]')
        obj_experience = CleanText('//li/span[text() = "Expérience requise : "]/following-sibling::span[1]')
        obj_formation = CleanText('//li/span[text() = "Niveau d\'études : "]/following-sibling::span[1]')
