# -*- CODing: utf-8 -*-

# Copyright(C) 2010-2011 Romain Bignon
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


from woob.tools.test import BackendTest


class GoogleTranslateTest(BackendTest):
    MODULE = "googletranslate"

    def test_MkEWBc_translate(self):
        tr = self.backend.translate("fr", "en", "je mange du chocolat")
        self.assertTrue(tr.text == "I'm eating chocolate")

    def test_AVdN8_translate(self):
        tr = self.backend.translate("fr", "en", "chocolat")
        self.assertTrue(tr.text == "chocolate")

    def test_long_text(self):
        text = """
        ya min tumaris alyahudiati! 'iidha kunt tadaei 'anak habib allah dun alakharin, fatamanaa almawt,
        'iidha kunt sadqan.
        """

        tr = self.backend.translate("ar", "tr", text)
        self.assertTrue(
            tr.text
            == "Hey, Yahudileri uygulayan! Ayrıca,"
            + " Tanrı'nın sevgilisi olduğunu iddia edersiniz, ölümü özlüyorum, ben de dürüstsiniz."
        )
