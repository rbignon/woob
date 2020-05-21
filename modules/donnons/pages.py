# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import datetime
import re

from woob.browser.pages import LoggedPage, HTMLPage
from woob.browser.elements import method, ListElement, ItemElement
from woob.browser.filters.standard import CleanText, Regexp
from woob.browser.filters.html import AbsoluteLink, Attr

from woob.capabilities.base import BaseObject, Field, StringField, BoolField
from woob.capabilities.date import DateField
from woob.tools.date import parse_french_date


class Ad(BaseObject):
    title = StringField('title')
    image_url = StringField('image')


class Thread(BaseObject):
    ad = Field('ad', Ad)
    last_activity = DateField('last activity')
    author = StringField('author')
    is_preferred = BoolField('is preferred?')
    last_is_us = BoolField('is last message from us?')


class Message(BaseObject):
    date = DateField('date')
    author = StringField('author')
    is_sent = BoolField('is sent?')
    message = StringField('message')
    thread = Field('thread', Thread)


class AdsThreadsPage(LoggedPage, HTMLPage):
    @method
    class iter_ads(ListElement):
        item_xpath = '//div[has-class("titre-annonce")]'

        class item(ItemElement):
            klass = Ad

            obj_title = CleanText('.//div[has-class("titre")]')
            obj_url = AbsoluteLink('.//div[has-class("titre")]/parent::a')
            obj_id = Regexp(obj_url, r'/(\d+)')
            obj_image_url = Attr('.//div[has-class("thumb-item")]/img', 'src')


class ThreadsPage(LoggedPage, HTMLPage):
    @method
    class iter_threads(ListElement):
        item_xpath = '//div[has-class("bloc-conversation") and has-class("f-item")]'

        # threads are in groups: e.g. with favorite person
        # but can appear in multiple groups (like "unread"), so ignore dupes
        ignore_duplicate = True

        class item(ItemElement):
            klass = Thread

            def obj_last_activity(self):
                txt = CleanText('.//div[has-class("date")]')(self).lower()
                txt = re.sub(r"\baujourd'hui\b", datetime.date.today().strftime('%Y-%m-%d'), txt)
                txt = re.sub(r"\bune\b", '1', txt)
                txt = re.sub(
                    r"\bhier\b",
                    (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d'), txt
                )
                txt = re.sub(r'\b(à|le)\b', '', txt)

                match = re.search(r'il y a (\d+) minutes?', txt)
                if match:
                    return datetime.datetime.now() - datetime.timedelta(minutes=int(match[1]))

                return parse_french_date(txt)

            # nickname is present multiple times
            obj_author = CleanText('(.//div/@data-pseudo)[1]')

            def obj_is_preferred(self):
                return bool(self.el.xpath('.//div[has-class("non-potentiel")]'))

            obj_url = AbsoluteLink('.//a[contains(@href, "/messagerie")]')
            obj_id = Regexp(obj_url, r'/\d+/(\d+)')

            def obj_last_is_us(self):
                return bool(self.el.xpath('.//i[has-class("fa-reply")]'))


class ThreadPage(LoggedPage, HTMLPage):
    @method
    class iter_ads(ListElement):
        item_xpath = '//div[has-class("titre-annonce")]'

        class item(ItemElement):
            klass = Ad

            obj_title = CleanText('.//div[has-class("titre")]')
            obj_url = AbsoluteLink('.//div[has-class("titre")]/parent::a')
            obj_id = Regexp(obj_url, r'/(\d+)')
            obj_image_url = Attr('.//div[has-class("thumb-item")]/img', 'src')


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(nr=0)
        form['email'] = username
        form['password'] = password
        form.submit()
