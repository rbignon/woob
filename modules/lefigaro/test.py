# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011  Romain Bignon
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


from woob.tools.html import html2text
from woob.tools.test import BackendTest
from woob.tools.value import Value


class LeFigaroTest(BackendTest):
    MODULE = "lefigaro"

    def setUp(self):
        if not self.is_backend_configured():
            self.backend.config["feed"] = Value(value="international")

    def test_lefigaro(self):
        self.backend.RSS_FEED = "http://www.lefigaro.fr/rss/figaro_%s.xml" % self.backend.config["feed"].get()
        l = list(self.backend.iter_threads())
        assert len(l)
        thread = self.backend.get_thread(l[0].id)
        assert len(thread.root.content)
        assert len(html2text(thread.root.content))
