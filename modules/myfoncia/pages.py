# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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

from __future__ import unicode_literals

from weboob.browser.pages import HTMLPage, LoggedPage
from weboob.browser.filters.standard import CleanDecimal, CleanText, Date, Env, Format
from weboob.browser.filters.html import Attr, Link, XPathNotFound, AbsoluteLink
from weboob.browser.elements import ItemElement, ListElement, method
from weboob.capabilities.base import NotAvailable
from weboob.capabilities.bill import Bill, Subscription, Document, DocumentTypes
from weboob.tools.compat import urljoin


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form('//form[@class="Form"]')

        form["username"] = username
        form["_password"] = password

        form.submit()


class MonBienPage(LoggedPage, HTMLPage):
    @method
    class get_subscriptions(ListElement):
        item_xpath = '//li[has-class("MyPropertiesSelector-item") and not(has-class("MyPropertiesSelector-item--add"))]'

        class item(ItemElement):
            klass = Subscription

            def obj_id(self):
                link = Link('./a')(self)
                return link[link.rfind('/') + 1:]

            obj_label = Format(
                '%s - %s (%s)',
                CleanText('.//strong[has-class("MyPropertiesSelector-item-title")]'),
                CleanText('.//span[has-class("MyPropertiesSelector-item-desc")][1]'),
                CleanText('.//span[has-class("MyPropertiesSelector-item-desc")][last()]')
            )

            def obj_subscriber(self):
                subscriber = CleanText('//a[has-class("MainNav-item-logged")]')(self)
                subscriber = subscriber.replace('Bonjour', '').strip()
                return subscriber


class MesChargesPage(LoggedPage, HTMLPage):
    @method
    class get_documents(ListElement):
        item_xpath = '//article[@data-taffy="utility_record"]'

        class item(ItemElement):
            klass = Bill

            obj_id = Format(
                '%s_%s',
                Env('subscription'),
                Attr('.', 'id')
            )

            obj_price = CleanDecimal('.//span[has-class("nbPrice")]',
                                     replace_dots=(',', '€'))

            obj_currency = u'EUR'

            def obj_income(self):
                price = CleanText('.//span[has-class("nbPrice")]')(self)
                return not price.startswith('−')

            obj_label = CleanText('.//p[has-class("TeaserRow-desc")]')
            obj_date = Date(CleanText('.//p[has-class("TeaserRow-date")]'),
                            dayfirst=True)
            obj_duedate = obj_date
            obj_format = "pdf"

            def obj_url(self):
                try:
                    return urljoin(
                        self.page.browser.BASEURL,
                        Link('.//a[has-class("Download")]')(self)
                    )
                except XPathNotFound:
                    return NotAvailable


class DocumentsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//main[@role="main"]//article'

        class item(ItemElement):
            klass = Document

            def condition(self):
                return CleanText('.//p[@data-behat="descOfUtilityRecord"]')(self) == 'CRG'

            obj_id = Format('%s_%s', Attr('.', 'id'), Env('subscription'))
            obj_date = Date(CleanText('.//p[@data-behat="dateOfUtilityRecord"]'), dayfirst=True)
            obj_label = CleanText('.//p[@data-behat="descOfUtilityRecord"]')
            obj_url = AbsoluteLink('.//a[@class="Download"]')
            obj_format = 'pdf'
            obj_type = DocumentTypes.REPORT
