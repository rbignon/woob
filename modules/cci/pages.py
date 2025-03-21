# Copyright(C) 2013      Bezleputh
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

from woob.browser.elements import ItemElement, TableElement, method
from woob.browser.filters.html import CleanHTML, Link, TableCell
from woob.browser.filters.standard import CleanText, DateTime, Env, Filter, Format, Join
from woob.browser.pages import HTMLPage
from woob.capabilities.job import BaseJobAdvert


class Child(Filter):
    def filter(self, el):
        return list(el[0].iterchildren())


class SearchPage(HTMLPage):
    @method
    class iter_job_adverts(TableElement):
        item_xpath = "//tr[position() > 1]"
        head_xpath = "//tr[1]/td[@class='titreCol2Tableau']/text()"

        col_place = "Région"
        col_job_name = "Filière"
        col_id = "Intitulé du poste"
        col_society_name = "CCI(R)"

        class item(ItemElement):
            klass = BaseJobAdvert

            def validate(self, advert):
                if advert and "pattern" in self.env and self.env["pattern"]:
                    return (
                        self.env["pattern"].upper() in advert.title.upper()
                        or self.env["pattern"].upper() in advert.job_name.upper()
                    )
                return True

            obj_id = CleanText(Link(Child(TableCell("id"))), replace=[("#", "")])
            obj_title = Format("%s - %s", CleanText(TableCell("id")), CleanText(TableCell("job_name")))
            obj_society_name = Format("CCI %s", CleanText(TableCell("society_name")))
            obj_place = CleanText(TableCell("place"))
            obj_job_name = CleanText(TableCell("id"))

    @method
    class get_job_advert(ItemElement):
        klass = BaseJobAdvert

        obj_url = Format("%s#%s", Env("url"), Env("id"))
        obj_description = Join(
            "\r\n", 'div/fieldset/*[(@class="titreParagraphe" or @class="normal")]', textCleaner=CleanHTML
        )
        obj_title = CleanText('div/span[@class="intituleposte"]')
        obj_job_name = CleanText('div/span[@class="intituleposte"]')
        obj_society_name = Format("CCI %s", CleanText('div/span[@class="crci crcititle"]'))
        obj_publication_date = DateTime(CleanText('div/fieldset/p[@class="dateOffre"]'), dayfirst=True)

        def parse(self, el):
            self.el = el.xpath("//div[@id=$id]/div", id=self.obj.id)[0]
            self.env["url"] = self.page.url
            self.env["id"] = self.obj.id
