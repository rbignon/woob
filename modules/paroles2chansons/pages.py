# Copyright(C) 2016 Julien Veyssier
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

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import CleanHTML
from woob.browser.filters.standard import CleanText, Regexp
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.lyrics import SongLyrics


class HomePage(HTMLPage):
    def search_lyrics(self, pattern):
        form = self.get_form(xpath='//form[@class="search-block"]')
        form["query"] = pattern
        form.submit()


class SearchPage(HTMLPage):
    @method
    class iter_song_lyrics(ListElement):
        item_xpath = '//p[text()="Chansons" and has-class("pull-left")]/../..//li[has-class("item")]'

        class item(ItemElement):
            klass = SongLyrics

            def obj_id(self):
                href = CleanText('.//a[has-class("link") and has-class("grey") and has-class("font-small")]/@href')(
                    self
                )
                subid = href.replace(".html", "").replace("paroles-", "").split("/")[-2:]
                id = f"{subid[0]}|{subid[1]}"
                return id

            obj_title = CleanText(
                './/a[has-class("link") and has-class("grey") and has-class("font-small")]', default=NotAvailable
            )
            obj_artist = CleanText(
                './/a[has-class("link") and has-class("black") and has-class("font-default")]', default=NotAvailable
            )
            obj_content = NotLoaded

    def get_artist_ids(self):
        artists_href = self.doc.xpath(
            '//p[text()="Artistes" and has-class("pull-left")]/../..//li[has-class("item")]//a[has-class("link")]/@href'
        )
        aids = [href.split("/")[-1].replace("paroles-", "") for href in artists_href]
        return aids


class ArtistPage(HTMLPage):
    @method
    class iter_lyrics(ListElement):
        item_xpath = '//p/text()[starts-with(.,"Toutes les")]/../../..//li[has-class("item") and has-class("clearfix")]'

        class item(ItemElement):
            klass = SongLyrics

            obj_title = CleanText('.//a[has-class("link")]', default=NotAvailable)
            obj_artist = Regexp(CleanText("//title"), "Paroles (.*) :.*")
            obj_content = NotLoaded

            def obj_id(self):
                href = CleanText('.//a[has-class("link")]/@href')(self)
                subid = href.replace(".html", "").replace("paroles-", "").split("/")[-2:]
                id = f"{subid[0]}|{subid[1]}"
                return id


class LyricsPage(HTMLPage):
    @method
    class get_lyrics(ItemElement):
        klass = SongLyrics

        def obj_id(self):
            subid = self.page.url.replace(".html", "").replace("paroles-", "").split("/")[-2:]
            id = f"{subid[0]}|{subid[1]}"
            return id

        obj_content = Regexp(
            CleanText(
                CleanHTML('//div[has-class("top-listing")]//div[has-class("text-center")]', default=NotAvailable),
                newlines=False,
            ),
            r"^(.*?)\s+Paroles2Chansons dispose d",
            flags=re.DOTALL,
        )
        obj_title = Regexp(CleanText("//title", default=NotAvailable), r"Paroles (.*) - .*")
        obj_artist = Regexp(CleanText("//title", default=NotAvailable), r"Paroles .* - (.*) \(tra.*")
