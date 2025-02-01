# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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


from woob.tools.test import BackendTest


class CodimdTest(BackendTest):
    MODULE = "codimd"

    def login_cb(self, backend_name, value):
        # accept empty credentials, that should be ok for features.md on the main domain
        return ""

    def test_get_simple(self):
        content = self.backend.get_content("features")
        assert content

        assert content.title
        assert content.title == "Features.md"

        assert content.content
        assert (
            content.content.startswith("# Features")
            # newer versions have yaml frontmatter
            or "\n# Features" in content.content
        )
