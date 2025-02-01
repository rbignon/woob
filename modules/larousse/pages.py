# Copyright(C) 2017      Vincent A
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
from woob.browser.filters.standard import CleanText, Env
from woob.browser.pages import HTMLPage
from woob.capabilities.translate import Translation


CODES = {
    "allemand": "de",
    "anglais": "en",
    "arabe": "ar",
    "chinois": "zh",
    "espagnol": "es",
    "francais": "fr",
    "italien": "it",
}

RCODES = {v: k for k, v in CODES.items()}


class LangList(HTMLPage):
    def get_langs(self):
        res = {}
        for a in self.doc.xpath('//a[@class="item-dico-bil"]'):
            url = a.attrib["href"]
            mtc = re.search(r"/dictionnaires/(\w+)-(\w+)", url)
            if not mtc:
                continue
            src, dst = mtc.groups()
            res[CODES[src], CODES[dst]] = (src, dst)
        return res


class WordPage(HTMLPage):
    @method
    class iter_translations(ListElement):
        item_xpath = '//span[has-class("Traduction") or has-class("Traduction2")][@lang]'

        class item(ItemElement):
            klass = Translation

            def condition(self):
                # ignore sub-translations
                parent = self.el.getparent()
                if parent.attrib.get("class", "") in ("Traduction", "Traduction2"):
                    return False

                if self.el.xpath('./ancestor::div[@class="BlocExpression" or @class="ZoneExpression"]'):
                    # example: http://larousse.fr/dictionnaires/francais-anglais/maison/48638
                    return False

                # ignore idioms translations
                for sibling in self.el.xpath("./preceding-sibling::*")[::-1]:
                    if sibling.tag == "br":
                        return True
                    if sibling.tag == "span" and sibling.attrib.get("class", "") == "Locution2":
                        return False
                    # TODO handle RTL text which is put in a sub div
                return True

            obj_lang_src = Env("src")
            obj_lang_dst = Env("dst")

            def obj_text(self):
                return re.sub(",", "", CleanText('./a[has-class("lienarticle2")]')(self)).strip()
