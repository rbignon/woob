# Copyright(C) 2011  Julien Hebert
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

from woob.browser.filters.html import CSS
from woob.browser.filters.standard import CleanText
from woob_modules.genericnewspaper.pages import GenericNewsPage


class ArticlePage(GenericNewsPage):
    _selector = CSS

    def on_load(self):
        self.main_div = self.doc.getroot()
        self.element_title_selector = "h1"
        self.element_author_selector = "p.author-sign, span.author-name"
        self.element_body_selector = "div[role=main], div.mna-body"

    def get_body(self):
        try:
            element_body = self.get_element_body()
        except AttributeError:
            return None
        else:
            self.try_remove(element_body, "figure")
            self.try_remove(element_body, self.element_author_selector)
            self.try_remove(element_body, "ul[class^=content-related]")
            self.try_remove(element_body, "*.mt2")
            self.try_remove(element_body, "*[class^=index]")
            self.try_remove(element_body, "p > a.highlight")
            self.try_remove(element_body, "script")
            self.try_remove(element_body, "blockquote")
            return CleanText(".")(element_body)
