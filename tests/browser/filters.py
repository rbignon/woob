# -*- coding: utf-8 -*-
# Copyright(C) 2016 Matthieu Weber
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

import datetime
from decimal import Decimal

from dateutil.tz import gettz
from lxml.html import fromstring

from woob.capabilities.base import NotAvailable
from woob.browser.filters.base import FilterError
from woob.browser.filters.html import FormValue, Link
from woob.browser.filters.standard import (
    RawText, DateTime, CleanText, Regexp, Currency, CleanDecimal, Date,
    NumberFormatError,
)
from woob.tools.test import TestCase


class TestRawText(TestCase):
    # Original RawText behaviour:
    # - the content of <p> is empty, we return the default value
    def test_first_node_is_element(self):
        e = fromstring('<html><body><p></p></body></html>')
        self.assertEqual("foo", RawText('//p', default="foo")(e))

    # - the content of <p> starts with text, we retrieve only that text
    def test_first_node_is_text(self):
        e = fromstring('<html><body><p>blah: <span>229,90</span> EUR</p></body></html>')
        self.assertEqual("blah: ", RawText('//p', default="foo")(e))

    # - the content of <p> starts with a sub-element, we retrieve the default value
    def test_first_node_has_no_recursion(self):
        e = fromstring('<html><body><p><span>229,90</span> EUR</p></body></html>')
        self.assertEqual("foo", RawText('//p', default="foo")(e))

    # Recursive RawText behaviour
    # - the content of <p> starts with text, we retrieve all text, also the text from sub-elements
    def test_first_node_is_text_recursive(self):
        e = fromstring('<html><body><p>blah: <span>229,90</span> EUR</p></body></html>')
        self.assertEqual("blah: 229,90 EUR", RawText('//p', default="foo", children=True)(e))

    # - the content of <p> starts with a sub-element, we retrieve all text, also the text from sub-elements
    def test_first_node_is_element_recursive(self):
        e = fromstring('<html><body><p><span>229,90</span> EUR</p></body></html>')
        self.assertEqual("229,90 EUR", RawText('//p', default="foo", children=True)(e))


class TestCleanTextNewlines(TestCase):
    def setUp(self):
        self.e = fromstring('''
        <body>
            <div>
                foo
                <span>bar</span>
                baz
            </div>
        </body>
        ''')

    def test_value(self):
        self.assertEqual("foo bar baz", CleanText("//div")(self.e))
        self.assertEqual("foo baz", CleanText("//div", children=False)(self.e))
        self.assertEqual("foo\nbar\nbaz", CleanText("//div", newlines=False)(self.e))
        self.assertEqual("foo\n\nbaz", CleanText("//div", newlines=False, children=False)(self.e))


class TestFormValue(TestCase):
    def setUp(self):
        self.e = fromstring('''
        <form>
            <input value="bonjour" name="test_text">
            <input type="number" value="5" name="test_number1">
            <input type="number" step="0.01" value="0.05" name="test_number2">
            <input type="checkbox" checked="on" name="test_checkbox1">
            <input type="checkbox" name="test_checkbox2">
            <input type="range" value="20" name="test_range">
            <input type="color" value="#fff666" name="test_color">
            <input type="date" value="2010-11-12" name="test_date">
            <input type="time" value="12:13" name="test_time">
            <input type="datetime-local" value="2010-11-12T13:14" name="test_datetime_local">
        </form>
        ''')

    def test_value(self):
        self.assertEqual('bonjour', FormValue('//form//input[@name="test_text"]')(self.e))
        self.assertEqual(5, FormValue('//form//input[@name="test_number1"]')(self.e))
        self.assertEqual(Decimal('0.05'), FormValue('//form//input[@name="test_number2"]')(self.e))
        self.assertEqual(True, FormValue('//form//input[@name="test_checkbox1"]')(self.e))
        self.assertEqual(False, FormValue('//form//input[@name="test_checkbox2"]')(self.e))
        self.assertEqual(20, FormValue('//form//input[@name="test_range"]')(self.e))
        self.assertEqual('#fff666', FormValue('//form//input[@name="test_color"]')(self.e))
        self.assertEqual(datetime.date(2010, 11, 12), FormValue('//form//input[@name="test_date"]')(self.e))
        self.assertEqual(datetime.time(12, 13), FormValue('//form//input[@name="test_time"]')(self.e))
        self.assertEqual(datetime.datetime(2010, 11, 12, 13, 14), FormValue('//form//input[@name="test_datetime_local"]')(self.e))


class TestLink(TestCase):
    def test_link(self):
        e = fromstring('<a href="https://www.google.com/">Google</a>')

        self.assertEqual('https://www.google.com/', Link('//a')(e))



class TestDateTime(TestCase):
    def test_tz(self):
        self.assertEqual(
            DateTime().filter('2020-01-02 13:45:00'),
            datetime.datetime(2020, 1, 2, 13, 45)
        )
        self.assertEqual(
            DateTime(tzinfo='Europe/Paris').filter('2020-01-02 13:45:00'),
            datetime.datetime(2020, 1, 2, 13, 45, tzinfo=gettz('Europe/Paris'))
        )



def test_CleanText():
    # This test works poorly under a doctest, or would be hard to read
    assert CleanText().filter(u' coucou  \n\théhé') == u'coucou héhé'
    assert CleanText().filter('coucou\xa0coucou') == CleanText().filter(u'coucou\xa0coucou') == u'coucou coucou'

    # Unicode normalization
    assert CleanText().filter(u'Éçã') == u'Éçã'
    assert CleanText(normalize='NFKC').filter(u'…') == u'...'
    assert CleanText().filter(u'…') == u'…'
    # Diacritical mark (dakuten)
    assert CleanText().filter(u'\u3053\u3099') == u'\u3054'
    assert CleanText(normalize='NFD').filter(u'\u3053\u3099') == u'\u3053\u3099'
    assert CleanText(normalize='NFD').filter(u'\u3054') == u'\u3053\u3099'
    assert CleanText(normalize=False).filter(u'\u3053\u3099') == u'\u3053\u3099'
    # None value
    assert_raises(FilterError, CleanText().filter, None)


def assert_raises(exc_class, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exc_class:
        pass
    else:
        assert False, 'did not raise %s' % exc_class


def test_CleanDecimal_unicode():
    assert CleanDecimal().filter(u'\u22123000') == Decimal('-3000')


def test_CleanDecimal_sign():
    assert CleanDecimal(sign='-').filter('42') == Decimal('-42')
    assert CleanDecimal(sign='-').filter('-42') == Decimal('-42')
    assert CleanDecimal(sign='+').filter('42') == Decimal('42')
    assert CleanDecimal(sign='+').filter('-42') == Decimal('42')


def test_CleanDecimal_strict():
    assert CleanDecimal.US().filter('123') == Decimal('123')
    assert CleanDecimal.US().filter('foo + 123 bar') == Decimal('123')
    assert CleanDecimal.US().filter('foo +123 bar') == Decimal('123')
    assert CleanDecimal.US().filter('foo 123.45 bar') == Decimal('123.45')
    assert CleanDecimal.US().filter('foo 12,345.67 bar') == Decimal('12345.67')
    assert CleanDecimal.US().filter('foo 123,456,789 bar') == Decimal('123456789')
    assert CleanDecimal.US().filter('foo - 123,456,789.1 bar') == Decimal('-123456789.1')
    assert CleanDecimal.US().filter('foo -123,456,789.1 bar') == Decimal('-123456789.1')
    assert CleanDecimal.US().filter('foo - .1 bar') == Decimal('-0.1')
    assert CleanDecimal.US().filter('foo -.1 bar') == Decimal('-0.1')
    assert_raises(NumberFormatError, CleanDecimal.US().filter, 'foo 12 345.67 bar')
    assert_raises(NumberFormatError, CleanDecimal.US().filter, 'foo 123 bar 456')
    assert_raises(NumberFormatError, CleanDecimal.US().filter, 'foo 123.456.789 bar')
    assert_raises(NumberFormatError, CleanDecimal.US().filter, 'foo 12,3456 bar')
    assert_raises(NumberFormatError, CleanDecimal.US().filter, 'foo 123-456 bar')

    assert CleanDecimal.French().filter('123') == Decimal('123')
    assert CleanDecimal.French().filter('foo + 123 bar') == Decimal('123')
    assert CleanDecimal.French().filter('foo +123 bar') == Decimal('123')
    assert CleanDecimal.French().filter('foo 123,45 bar') == Decimal('123.45')
    assert CleanDecimal.French().filter('foo 12 345,67 bar') == Decimal('12345.67')
    assert CleanDecimal.French().filter('foo - 123 456 789 bar') == Decimal('-123456789')
    assert CleanDecimal.French().filter('foo -123 456 789 bar') == Decimal('-123456789')
    assert_raises(NumberFormatError, CleanDecimal.French().filter, 'foo 123.45 bar')
    assert_raises(NumberFormatError, CleanDecimal.French().filter, 'foo 123 bar 456')
    assert_raises(NumberFormatError, CleanDecimal.French().filter, 'foo 123,456,789')
    assert_raises(NumberFormatError, CleanDecimal.French().filter, 'foo 12 3456 bar')
    assert_raises(NumberFormatError, CleanDecimal.French().filter, 'foo 123-456 bar')

    assert CleanDecimal.SI().filter('123') == Decimal('123')
    assert CleanDecimal.SI().filter('foo + 123 bar') == Decimal('123')
    assert CleanDecimal.SI().filter('foo +123 bar') == Decimal('123')
    assert CleanDecimal.SI().filter('foo 123.45 bar') == Decimal('123.45')
    assert CleanDecimal.SI().filter('foo 12 345.67 bar') == Decimal('12345.67')
    assert CleanDecimal.SI().filter('foo 123 456 789 bar') == Decimal('123456789')
    assert CleanDecimal.SI().filter('foo - 123 456 789 bar') == Decimal('-123456789')
    assert CleanDecimal.SI().filter('foo -123 456 789 bar') == Decimal('-123456789')
    assert_raises(NumberFormatError, CleanDecimal.SI().filter, 'foo 123,45 bar')
    assert_raises(NumberFormatError, CleanDecimal.SI().filter, 'foo 123 bar 456')
    assert_raises(NumberFormatError, CleanDecimal.SI().filter, 'foo 123,456,789')
    assert_raises(NumberFormatError, CleanDecimal.SI().filter, 'foo 12 3456 bar')
    assert_raises(NumberFormatError, CleanDecimal.SI().filter, 'foo 123-456 bar')

def test_Currency():
    assert Currency().filter(u'\u20AC') == 'EUR'
    assert Currency(default=NotAvailable).filter(None) == NotAvailable
    assert_raises(FilterError, Currency().filter, None)

def test_DateTime():
    today = datetime.datetime.now()
    assert_raises(FilterError, Date(strict=True).filter, '2019')
    assert_raises(FilterError, Date(strict=True).filter, '1788-7')
    assert_raises(FilterError, Date(strict=True).filter, 'June 1st')

    assert Date(strict=True).filter('1788-7-15') == datetime.date(1788, 7, 15)

    assert Date(strict=False).filter('1788-7-15') == datetime.date(1788, 7, 15)
    assert Date(strict=False).filter('1945-7') == datetime.date(1945, 7, today.day)
    assert Date(strict=False).filter('June 1st') == datetime.date(today.year, 6, 1)

    assert DateTime(strict=False).filter('1788-7') == datetime.datetime(1788, 7, today.day)
    assert DateTime(strict=False).filter('1788') == datetime.datetime(1788, today.month, today.day)
    assert DateTime(strict=False).filter('5-1') == datetime.datetime(today.year, 5, 1)

    assert Date(yearfirst=True).filter('88-7-15') == datetime.date(1988, 7, 15)
    assert Date(yearfirst=False).filter('20-7-15') == datetime.date(2015, 7, 20)
    assert Date(yearfirst=True).filter('1789-7-15') == datetime.date(1789, 7, 15)
    assert Date(yearfirst=True, strict=False).filter('7-15') == datetime.date(today.year, 7, 15)


def test_regex():
    try:
        assert Regexp(pattern=r'([[a-z]--[aeiou]]+)(?V1)').filter(u'abcde') == u'bcd'
        assert not Regexp(pattern=r'([[a-z]--[aeiou]]+)(?V0)', default=False).filter(u'abcde')
    except ImportError:
        pass
    assert not Regexp(pattern=r'([[a-z]--[aeiou]]+)', default=False).filter(u'abcde')
