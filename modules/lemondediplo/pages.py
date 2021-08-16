# -*- coding: utf-8 -*-

# Copyright(C) 2021      Bezleputh
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

from __future__ import unicode_literals

from woob.tools.date import parse_french_date
from woob.capabilities.messages import Thread, Message
from woob.browser.filters.standard import CleanText, Regexp, Env, Date
from woob.browser.filters.html import CleanHTML
from woob.browser.filters.html import XPath
from woob.browser.pages import HTMLPage
from woob.browser.elements import ItemElement, ListElement, method


class LoginPage(HTMLPage):
    def login(self, login, passwd):
        form = self.get_form()
        form['email'] = login
        form['mot_de_passe'] = passwd
        form.submit()


class LoginErrorPage(HTMLPage):
    pass


class BlogsPage(HTMLPage):

    @method
    class iter_blog_thread(ListElement):
        # TODO pagination

        item_xpath = '//a[@class="yalogo"]'

        class item(ItemElement):
            klass = Thread

            obj_title = CleanText('./div/h3')
            obj_id = CleanText('./@href')

            def obj_date(self):
                date = Regexp(CleanText('./div/div[@class="dates_auteurs"]', children=False),
                              r'.*(\w* \d{4})')(self)
                return parse_french_date(date)

    @method
    class get_thread(ItemElement):
        klass = Thread

        obj_id = Env('id')
        obj_title = CleanText('//h1')

        def obj_date(self):
            date = Regexp(CleanText('//div[has-class("calcul_date")]', children=False),
                          r'.*(\w* \d{4})$')(self)
            return parse_french_date(date)

    @method
    class get_article(ItemElement):
        klass = Message

        obj_id = Env('id')
        obj_title = CleanText('//h1')

        def obj_date(self):
            date = Regexp(CleanText('//div[has-class("calcul_date")]', children=False),
                          r'.*(\w* \d{4})$')(self)
            return parse_french_date(date)

        obj_content = CleanHTML('//div[has-class("texte")]')
        obj_sender = CleanText('//div[@class="lesauteurs"]')


class ArticlesPage(HTMLPage):

    @property
    def logged(self):
        return XPath('//a[@id="session_deconnexion"]')(self.doc)

    @method
    class iter_threads(ListElement):
        item_xpath = '//a[has-class("yalogo")]'

        class item(ItemElement):
            klass = Thread

            def condition(self):
                return XPath('./div[@class="unarticle"]', default=False)(self) and\
                       not CleanText('./@href')(self).startswith('/podcast')

            obj_title = CleanText('./div/div/h3')
            obj_id = Regexp(CleanText('./@href'), '/(.*)')

            def obj_date(self):
                date = Regexp(CleanText('./div/div/div', children=False),
                              r'.*(\w* \d{4})')(self)
                return parse_french_date(date)

    @method
    class iter_archive_threads(ListElement):
        item_xpath = '//a'

        class item(ItemElement):
            klass = Thread

            def condition(self):
                return Regexp(CleanText('./@href'),
                              fr'^/{Env("id")(self)}\w+/\d+$',
                              default=False)(self)

            obj_title = CleanText('./div/h3|./div/div/h3|./div/div/div/h3|./div/h4')
            obj_id = Regexp(CleanText('./@href'), '/(.*)')

            def obj_date(self):
                date = CleanText('//head/meta[@property="og:title"]/@content')(self)
                return parse_french_date(date)

    @method
    class get_thread(ItemElement):
        klass = Thread

        obj_id = Env('id')
        obj_title = CleanText('//h1')

        obj_date = Date(Regexp(CleanText('//a[@class="filin"]/@href'),
                               r'/(\d{4})/(\d{2})/',
                               '01/\\2/\\1'))

    @method
    class get_article(ItemElement):
        klass = Message

        obj_id = Env('id')
        obj_title = CleanText('//h1')

        obj_date = Date(Regexp(CleanText('//a[@class="filin"]/@href'),
                               r'/(\d{4})/(\d{2})/',
                               '01/\\2/\\1'))

        def obj_content(self):
            sub_id = Env('id')(self).split('/')[-1]
            return CleanHTML(f'//div[has-class("article-texte-{sub_id}")]/p')(self)

        obj_sender = CleanText('//div[has-class("dates_auteurs")]/span[@class="auteurs"]|//div[@class="lesauteurs"]/p',
                               children=False)
