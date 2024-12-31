# -*- coding: utf-8 -*-

# Copyright(C) 2013 Florent Fourcot
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

from woob.browser.filters.html import CSS, XPathNotFound
from woob.browser.filters.standard import CleanText
from woob_modules.genericnewspaper.pages import GenericNewsPage


class ArticlePage(GenericNewsPage):
    _selector = CSS

    def on_loaded(self):
        self.main_div = self.doc.getroot()
        self.element_title_selector = "head>title"
        self.element_author_selector = "span.author"
        self.element_body_selector = "div.article-body, div[itemprop=articleBody]"

    def get_body(self):
        if '.blogs.liberation.fr/' in self.url:
            self.element_body_selector = "div.entry-content"
        try:
            element_body = self.get_element_body()
            self.try_remove(element_body, "script")
            return CleanText('.')(element_body)
        except XPathNotFound:
            meta = self.doc.xpath('//meta[@name="description"]')[0]
            txt = meta.attrib['content']
            return txt
        except AttributeError:
            return "No content found"

    def get_title(self):
        title = super(self.__class__, self).get_title()
        return title.replace(u' - Libération', '')

    def get_author(self):
        try:
            author = CleanText('.')(self.get_element_author())
            if author.startswith('Par '):
                return author.split('Par ', 1)[1]
            else:
                return author
        except AttributeError:
            return ''
