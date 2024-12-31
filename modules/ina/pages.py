# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Romain Bignon
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
from datetime import datetime, timedelta

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanText, Date, Duration, Env, Regexp
from woob.browser.pages import HTMLPage, JsonPage, PartialHTMLPage, pagination
from woob.capabilities.audio import BaseAudio
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import Thumbnail
from woob.capabilities.video import BaseVideo
from woob.tools.capabilities.audio.audio import BaseAudioIdFilter


class InaDuration(Duration):
    _regexp = re.compile(r'(?P<hh>\d+):(?P<mm>\d+):(?P<ss>\d+)')
    kwargs = {'minutes': 'mm', 'seconds': 'ss'}


class InaDuration2(Duration):
    _regexp = re.compile(r'(?P<mm>\d+):(?P<ss>\d+)')
    kwargs = {'minutes': 'mm', 'seconds': 'ss'}


class InaListElement(ListElement):
    item_xpath = '//div[has-class("contentResult")]'

    def next_page(self):
        offset = CleanText('//div[@class="progress-bar"]/@aria-valuenow')(self)
        valuemax = CleanText('//div[@class="progress-bar"]/@aria-valuemax')(self)
        if offset <= valuemax:
            first_item = int(Env('first_item')(self)) + int(offset)
            return BrowserURL('search_page',
                              pattern=Env('pattern'),
                              type=Env('type'),
                              first_item=first_item)(self)


class InaItemElement(ItemElement):
    def obj_title(self):
        __ = CleanText('./a/div[has-class("title-bloc-small")]')(self)
        _ = CleanText('./a/div[has-class("dateAgenda")]')(self).split('-')[0]
        return fr"{__} - {_}"

    def obj_duration(self):
        duration = InaDuration(CleanText('./a/div[has-class("dateAgenda")]'),
                               default=None)(self)
        if duration is None:
            duration = InaDuration2(CleanText('./a/div[has-class("dateAgenda")]'),
                                    default=NotAvailable)(self)
        return duration

    obj_author = u'Institut National de l’Audiovisuel'

    def obj_date(self):
        dt = Regexp(CleanText('./a/div[has-class("dateAgenda")]'),
                    r'.*- (\d{2}/\d{2}/\d{4}) -.*',
                    default=False)(self)
        if not dt:
            dt = Regexp(CleanText('./a/div[has-class("dateAgenda")]'),
                        r'(\d{4}) -.*', '01/01/\\1',
                        default=False)(self)

        if not dt:
            return NotAvailable

        return datetime.strptime(dt, '%d/%m/%Y')

    def obj_thumbnail(self):
        url = CleanText('./a/div/img/@data-src')(self)
        thumbnail = Thumbnail(url)
        thumbnail.url = thumbnail.id
        return thumbnail


class InaMediaElement(ItemElement):
    obj_title = Dict('title')
    obj_description = Dict('description')
    obj_date = Date(Dict('dateOfBroadcast'))
    obj_author = u'Institut National de l’Audiovisuel'
    obj_url = Dict('resourceUrl')

    def obj_duration(self):
        _ = Dict('duration')(self)
        return timedelta(seconds=_)

    def obj_thumbnail(self):
        url = Dict('resourceThumbnail')(self)
        thumbnail = Thumbnail(url)
        thumbnail.url = thumbnail.id
        return thumbnail


class SearchPage(PartialHTMLPage):

    @pagination
    @method
    class iter_audios(InaListElement):
        class item(InaItemElement):
            klass = BaseAudio

            def condition(self):
                return Regexp(CleanText('./a/@href'),
                              '/ina-eclaire-actu/audio/(.*)/.*',
                              default=None)(self)

            obj_id = BaseAudioIdFilter(Regexp(CleanText('./a/@href'),
                                              '/ina-eclaire-actu/audio/(.*)/.*'))

    @pagination
    @method
    class iter_videos(InaListElement):
        class item(InaItemElement):
            klass = BaseVideo

            def condition(self):
                return Regexp(CleanText('./a/@href'),
                              '/ina-eclaire-actu/video/(.*)/.*',
                              default=None)(self)

            obj_id = Regexp(CleanText('./a/@href'), '/ina-eclaire-actu/video/(.*)/.*')


class MediaPage(HTMLPage):
    def get_player_url(self):
        return CleanText('//div[@data-type="player"]/@asset-details-url')(self.doc)


class PlayerPage(JsonPage):

    @method
    class get_audio(InaMediaElement):
        klass = BaseAudio
        obj_ext = u'mp3'
        obj_id = Env('id')

    @method
    class get_video(InaMediaElement):
        klass = BaseVideo
        obj_ext = u'mp4'
        obj_id = Env('id')
