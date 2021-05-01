from lxml.html import fromstring

from woob.tools.test import TestCase


class DistinctValuesTest(TestCase):
    def setUp(self):
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
        self.assertEqual(
            self.identity.xpath('distinct-values(//div[@id="identity"]//span[@id="lastname"]/text())'), ['Asimov']
        )
        self.assertEqual(self.identity.xpath('distinct-values(//span[@id="firstname"]/text())'), ['Isaac'])
        self.assertEqual(self.identity.xpath('distinct-values(//a[@class="book-1"]/text())'), ['Foundation'])

    def test_that_distinct_inexistent_values_return_empty_value(self):
        self.assertEqual(self.identity.xpath('distinct-values(//a[@class="book-4"]/text())'), [])

    def test_that_different_values_are_successfully_returns_as_is(self):
        self.assertEqual(
            set(self.identity.xpath('distinct-values(//a[@class="book-3"]/text())')),
            set(["Foundation's Edge", 'Second Foundation'])
        )
