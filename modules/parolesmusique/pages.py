# -*- coding: utf-8 -*-

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


import random

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import CleanHTML
from woob.browser.filters.standard import CleanText, Format, Regexp
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.lyrics import SongLyrics


class HomePage(HTMLPage):
    def search_lyrics(self, criteria, pattern):
        form = self.get_form(xpath='//form[@name="rechercher"]')
        form['query'] = pattern
        if criteria == 'artist':
            form['termes_a'] = pattern
        else:
            form['termes_t'] = pattern
        form.submit()


class ArtistResultsPage(HTMLPage):
    def get_artist_ids(self):
        artists_href = self.doc.xpath('//div[has-class("cont_cat")]//a[has-class("matchA")]/@href')
        aids = [href.split('/')[-1].replace('paroles-','') for href in artists_href]
        return aids


class ArtistSongsPage(HTMLPage):
    @method
    class iter_lyrics(ListElement):
        item_xpath = '//td[has-class("art_titr")]//a'

        class item(ItemElement):
            klass = SongLyrics

            obj_title = CleanText('.', default=NotAvailable)
            obj_artist = CleanText('//h1[@id="art_title"]', default=NotAvailable)
            # little trick because the damn site potentially shows identical songs in results
            # the dummy added prefix number does not annoy the module
            # it seems this part of the URL is not red anyway
            def obj_id(self):
                res = Format('%s%s',
                        int(random.random()*100000),
                        Regexp(CleanText('./@href', default=NotAvailable), 'paroles-(.*)'))(self)
                return res
            obj_content = NotLoaded


class SongResultsPage(HTMLPage):
    @method
    class iter_lyrics(ListElement):
        item_xpath = '//div[has-class("cont_cat")]//table//tr[position() > 1]'

        class item(ItemElement):
            klass = SongLyrics

            obj_title = CleanText('.//a[has-class("matchT")]', default=NotAvailable)
            obj_id = Regexp(CleanText('.//a[has-class("matchT")]/@href', default=NotAvailable), 'paroles-(.*)')
            obj_artist = CleanText('.//a[has-class("matchA")]', default=NotAvailable)
            obj_content = NotLoaded


class SonglyricsPage(HTMLPage):
    @method
    class get_lyrics(ItemElement):
        klass = SongLyrics

        obj_content = CleanText(CleanHTML('//div[@id="lyr_scroll"]', default=NotAvailable), newlines=False)
        obj_title = CleanText('//div[@id="main_ct"]//ul[has-class("semiopaquemenu")]//li[position()=3]', default=NotAvailable)
        obj_artist = CleanText('//div[@id="main_ct"]//ul[has-class("semiopaquemenu")]//li[position()=2]', default=NotAvailable)
        obj_id = Regexp(CleanText('//div[@id="main_ct"]//ul[has-class("semiopaquemenu")]//li[position()=3]//a/@href', default=NotAvailable),
                 'paroles-(.*)')

