# -*- coding: utf-8 -*-

# Copyright(C) 2013 Julien Veyssier
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
from woob.browser.filters.html import CleanHTML
from woob.browser.filters.standard import CleanText, Regexp
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.lyrics import SongLyrics


class SearchSongPage(HTMLPage):
    @method
    class iter_lyrics(ListElement):
        item_xpath = '//div[has-class("elenco")]//div[has-class("col-left")]//li//a[starts-with(@href, "/paroles") and not(contains(@href, "alpha.html"))]'

        class item(ItemElement):
            klass = SongLyrics

            def obj_id(self):
                href = CleanText('./@href')(self)
                subid = href.replace('.html','').replace('paroles_','').split('/')[-2:]
                id = '%s|%s'%(subid[0], subid[1])
                return id
            obj_title = Regexp(CleanText('.', default=NotAvailable), '(.*) - .*')
            obj_artist = Regexp(CleanText('.', default=NotAvailable), '.* - (.*)')
            obj_content = NotLoaded


class SearchArtistPage(HTMLPage):
    def get_artist_ids(self):
        artists_href = self.doc.xpath('//div[has-class("elenco")]//div[has-class("col-left")]//li//a/@href')
        aids = [href.split('/')[-1].replace('paroles_', '').replace('.html', '') for href in artists_href]
        return aids


class ArtistSongsPage(HTMLPage):
    @method
    class iter_lyrics(ListElement):
        item_xpath = '//div[has-class("album")]//ul//li//a[starts-with(@href, "/paroles") and not(contains(@href, "alpha.html"))]'

        class item(ItemElement):
            klass = SongLyrics

            obj_title = CleanText('.', default=NotAvailable)
            obj_artist = Regexp(CleanText('//head/title'), 'Paroles (.*)')
            obj_content = NotLoaded
            def obj_id(self):
                href = CleanText('./@href')(self)
                subid = href.replace('.html','').replace('paroles_','').split('/')[-2:]
                id = '%s|%s'%(subid[0], subid[1])
                return id


class LyricsPage(HTMLPage):
    @method
    class get_lyrics(ItemElement):
        klass = SongLyrics

        def obj_id(self):
            subid = self.page.url.replace('.html','').replace('paroles_','').split('/')[-2:]
            id = '%s|%s'%(subid[0], subid[1])
            return id
        obj_content = CleanText(CleanHTML('//div[has-class("lyrics-body")]/*[not(contains(@id, "video"))]', default=NotAvailable), newlines=False)
        obj_title = Regexp(CleanText('//title', default=NotAvailable), 'Paroles (.*) - .*')
        obj_artist = Regexp(CleanText('//title', default=NotAvailable), 'Paroles .* - (.*)')
