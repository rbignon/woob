# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

import datetime
import re

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import AbsoluteLink, Attr
from woob.browser.filters.standard import CleanText, Regexp
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.base import BaseObject, BoolField, Field, StringField
from woob.capabilities.date import DateField
from woob.capabilities.messages import Message as BaseMessage
from woob.capabilities.messages import Thread as BaseThread
from woob.tools.date import parse_french_date
from woob.tools.json import json


# dedicated cap objects
# TODO new cap?


class Ad(BaseObject):
    title = StringField("Ad title")
    image_url = StringField("Ad image URL")


class Thread(BaseThread):
    ad = Field("Ad", Ad)
    last_activity = DateField("Last activity time")
    sender = StringField("Author")
    is_preferred = BoolField("Is favorite?")
    last_is_us = BoolField("Is last message from us?")


class Message(BaseMessage):
    is_sent = BoolField("Is it sent?")


# helpers


def parse_fuzzy_date(txt):
    txt = txt.lower()
    txt = re.sub(r"\baujourd'hui\b", datetime.date.today().strftime("%Y-%m-%d"), txt)
    txt = re.sub(r"\bune\b", "1", txt)
    txt = re.sub(r"\bhier\b", (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"), txt)
    txt = re.sub(r"\b(à|le)\b", "", txt)

    match = re.search(r"il y a (\d+) minutes?", txt)
    if match:
        return datetime.datetime.now() - datetime.timedelta(minutes=int(match[1]))

    return parse_french_date(txt)


# pages


class AdsThreadsPage(LoggedPage, HTMLPage):
    @method
    class iter_ads(ListElement):
        item_xpath = '//div[has-class("titre-annonce")]'

        class item(ItemElement):
            klass = Ad

            obj_title = CleanText('.//div[has-class("titre")]')
            obj_url = AbsoluteLink('.//div[has-class("titre")]/parent::a')
            obj_id = Regexp(obj_url, r"/(\d+)")
            obj_image_url = Attr('.//div[has-class("thumb-item")]/img', "src")


class ThreadsPage(LoggedPage, HTMLPage):
    @method
    class iter_threads(ListElement):
        item_xpath = '//div[has-class("bloc-conversation") and has-class("f-item")]'

        # threads are in groups: e.g. with favorite person
        # but can appear in multiple groups (like "unread"), so ignore dupes
        ignore_duplicate = True

        class item(ItemElement):
            klass = Thread

            obj_flags = Thread.IS_DISCUSSION

            def obj_last_activity(self):
                return parse_fuzzy_date(CleanText('.//div[has-class("date")]')(self))

            # nickname is present multiple times
            obj_sender = CleanText("(.//div/@data-pseudo)[1]")

            def obj_is_preferred(self):
                return bool(self.el.xpath('.//div[has-class("non-potentiel")]'))

            obj_url = AbsoluteLink('.//a[contains(@href, "/messagerie")]')
            obj_id = Regexp(obj_url, r"/(\d+)/(\d+)", r"\1.\2")

            def obj_last_is_us(self):
                return bool(self.el.xpath('.//i[has-class("fa-reply")]'))


class ThreadPage(LoggedPage, HTMLPage):
    def get_total_count(self):
        try:
            (text,) = self.doc.xpath("//button[@id='load-messages']/@data-max")
        except ValueError:
            return 0
        else:
            return int(text)

    @method
    class iter_messages(ListElement):
        item_xpath = '//div[starts-with(@id, "message_")]'

        class item(ItemElement):
            klass = Message

            obj_content = CleanText(".//div[has-class('peekboo')]", newlines=False)

            def obj_is_sent(self):
                div = self.el.xpath(".//div[has-class('peekboo')]")[0]
                return "moi" in div.attrib["class"]

            def obj_date(self):
                return parse_fuzzy_date(CleanText(".//div[@class='datelu']/span[@class='highlight']")(self))

            obj_sender = CleanText(".//div[has-class('avatar-box')]")

            obj_id = Regexp(Attr(".", "id"), "message_(.*)")


class ThreadNextPage(LoggedPage, HTMLPage):
    def build_doc(self, content):
        j = json.loads(content)
        return super().build_doc(j["result"].encode("utf-8"))

    @method
    class iter_messages(ListElement):
        item_xpath = '//div[starts-with(@id, "message_")]'

        class item(ItemElement):
            klass = Message

            obj_content = CleanText(".//div[has-class('peekboo')]", newlines=False)

            def obj_is_sent(self):
                div = self.el.xpath(".//div[has-class('peekboo')]")[0]
                return "moi" in div.attrib["class"]

            def obj_date(self):
                return parse_fuzzy_date(CleanText(".//div[@class='datelu']/span[@class='highlight']")(self))

            obj_sender = CleanText(".//div[has-class('avatar-box')]")

            obj_id = Regexp(Attr(".", "id"), "message_(.*)")


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(nr=0)
        form["email"] = username
        form["password"] = password
        form.submit()
