# Copyright(C) 2012 Romain Bignon
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

from woob.browser.pages import HTMLPage


def fix_form(form):
    keys = [
        "MM$HISTORIQUE_COMPTE$btnCumul",
        "Cartridge$imgbtnMessagerie",
        "MM$m_CH$ButtonImageFondMessagerie",
        "MM$m_CH$ButtonImageMessagerie",
    ]
    for name in keys:
        form.pop(name, None)


class BasePage(HTMLPage):
    def build_doc(self, content):
        # don't know if it's still relevant...
        content = content.strip(b"\x00")
        return super().build_doc(content)
