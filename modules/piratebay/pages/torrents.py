# Copyright(C) 2010-2021 Julien Veyssier
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

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.standard import CleanText, Date, RawText, Regexp, Type
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.torrent import Torrent
from woob.tools.misc import get_bytes_size


class TorrentsPage(HTMLPage):
    @method
    class iter_torrents(ListElement):
        item_xpath = '//table[@id="searchResult"]/tr'

        class item(ItemElement):
            klass = Torrent

            obj_id = Regexp(CleanText('./td[2]/div/a[@class="detLink"]/@href'), r"^/torrent/(\d+)/", "\\1")
            obj_name = Regexp(CleanText('./td[2]/div/a[@class="detLink"]/@title'), r"Details for (.*)$", "\\1")
            obj_magnet = CleanText('./td[2]/a[title="Download this torrent using magnet"]/@href')
            obj_date = Date(Regexp(CleanText("./td[2]/font"), r"Uploaded ([^,]+),", "\\1"), fuzzy=True)
            obj_seeders = Type(CleanText("./td[3]"), type=int)
            obj_leechers = Type(CleanText("./td[4]"), type=int)

            def obj_size(self):
                value, unit = Regexp(CleanText("./td[2]/font"), r"Size ([\d\.]+ [^,]+),", "\\1")(self).split(" ")
                return get_bytes_size(float(value), unit)


class TorrentPage(HTMLPage):
    @method
    class get_torrent(ItemElement):
        klass = Torrent

        def obj_id(self):
            return self.page.url.split("/")[-1]

        def obj_url(self):
            return NotAvailable

        obj_name = CleanText('//div[@id="title"]')
        obj_magnet = CleanText('//div[@class="download"]/a[starts-with(@href, "magnet:")]/@href')
        obj_date = Date(CleanText('//div[@id="details"]//dt[.="Uploaded:"]/following-sibling::dd[1]'))
        obj_size = Type(
            Regexp(
                CleanText('//div[@id="details"]//dt[.="Size:"]/following-sibling::dd[1]'), r"\((\d+) Bytes\)", "\\1"
            ),
            type=float,
        )
        obj_seeders = Type(CleanText('//div[@id="details"]//dt[.="Seeders:"]/following-sibling::dd[1]'), type=int)
        obj_leechers = Type(CleanText('//div[@id="details"]//dt[.="Leechers:"]/following-sibling::dd[1]'), type=int)
        obj_description = RawText('//div[@class="nfo"]/pre', children=True)


class FilesPage(HTMLPage):
    def get_files(self):
        return [" ".join([td.text for td in tr.xpath("./td")]) for tr in self.doc.xpath("//table/tr")]
