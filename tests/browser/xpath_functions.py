# -*- coding: utf-8 -*-
# Copyright(C) 2021 woob project
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from lxml.html import fromstring

from woob.browser.pages import HTMLPage
from woob.tools.test import TestCase


class HasClassTest(TestCase):
    def setUp(self):
        HTMLPage.setup_xpath_functions()

        self.root = fromstring('''
            <a>
                <b class="one first text">I</b>
                <b class="two text">LOVE</b>
                <b class="three text">CSS</b>
            </a>
            ''')

    def test_that_has_class_return_expected_result(self):
        assert len(self.root.xpath('//b[has-class("text")]')) == 3
        assert len(self.root.xpath('//b[has-class("one")]')) == 1
        assert len(self.root.xpath('//b[has-class("text", "first")]')) == 1
        assert len(self.root.xpath('//b[not(has-class("first"))]')) == 2
        assert len(self.root.xpath('//b[has-class("not-exists")]')) == 0


class TestDistinctValues(TestCase):
    def setUp(self):
        HTMLPage.setup_xpath_functions()

        self.identity = fromstring('''
            <body>
                <div id="identity">
                    <span id="firstname">Isaac</span>
                    <span id="lastname">Asimov</span>
                    <span id="birthday">02/01/1920</span>
                    <span id="job">Writer</span>
                    <span id="gender">M</span>
                    <span id="adress">651 Essex Street</span>
                    <span id="city">Brooklyn</span>
                </div>
                <div id="identity">
                    <span id="firstname">Isaac</span>
                    <span id="lastname">Asimov</span>
                    <span id="birthday">02/01/1920</span>
                    <span id="job">Writer</span>
                    <span id="gender">M</span>
                    <span id="adress">651 Essex Street</span>
                    <span id="city">Brooklyn</span>
                </div>
                <div id="bibliography">
                <a id="Foundation" class="book-1" href="#">Foundation</a>
                <a id="Foundation" class="book-1" href="#">Foundation</a>
                <a id="Foundation and Empire" class="book-2" href="#">Foundation and Empire</a>
                <a id="Foundation and Empire" class="book-2" href="#">Foundation and Empire</a>
                <a id="Second Foundation" class="book-3" href="#">Second Foundation</a>
                <a id="Foundation’s Edge" class="book-3" href="#">Foundation's Edge</a>
                </div>
            </body>
        ''')

    def test_that_values_are_successfully_distinct(self):
        assert (
            self.identity.xpath('distinct-values(//div[@id="identity"]//span[@id="lastname"]/text())') == ['Asimov']
        )
        assert self.identity.xpath('distinct-values(//span[@id="firstname"]/text())') == ['Isaac']
        assert self.identity.xpath('distinct-values(//a[@class="book-1"]/text())') == ['Foundation']

    def test_that_distinct_inexistent_values_return_empty_value(self):
        assert self.identity.xpath('distinct-values(//a[@class="book-4"]/text())') == []

    def test_that_different_values_are_successfully_returns_as_is(self):
        assert (
            set(self.identity.xpath('distinct-values(//a[@class="book-3"]/text())'))
            == set(["Foundation's Edge", 'Second Foundation'])
        )
