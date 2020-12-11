# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re

from weboob.browser.pages import LoggedPage, HTMLPage
from weboob.capabilities.bill import Document, DocumentTypes, Subscription
from weboob.browser.elements import ListElement, ItemElement, method
from weboob.browser.filters.standard import Env, CleanText, Date, Regexp, Format
from weboob.browser.filters.html import Link


class SubscriptionsTransitionPage(LoggedPage, HTMLPage):
    def submit(self, token):
        form = self.get_form(name='formulaire')
        form[':cq_csrf_token'] = token
        form['largeur_ecran'] = 1920
        form['hauteur_ecran'] = 1080
        form.submit()


class SubscriptionsDocumentsPage(LoggedPage, HTMLPage):
    def has_error(self):
        return bool(CleanText('//h1[contains(text(), "Erreur de téléchargement")]')(self.doc))

    @method
    class iter_subscription(ListElement):
        item_xpath = '//div[contains(text(), "RELEVES DE COMPTES")]/following-sibling::table//tr//div[contains(@class, "table")]'

        class item(ItemElement):
            klass = Subscription

            def get_account_information(self):
                raw = CleanText('./a')(self)
                # raw = account_name account_id account_owner
                m = re.match(r'([A-Za-z ]+) (\d+) (.+)$', raw)
                assert m, 'Format of line is not: ACT 123456789 M. First Last'
                return m.groups()

            def condition(self):
                # We check if the subscription hasn't been already parsed
                _, account_id, _ = self.get_account_information()
                return account_id not in Env('parsed_subscription_ids')(self)

            def parse(self, el):
                self.env['account_name'], self.env['account_id'], self.env['account_owner'] = self.get_account_information()

            obj_label = Format('%s %s', Env('account_name'), Env('account_owner'))
            obj_subscriber = Env('account_owner')
            obj_id = Env('account_id')

    def get_document_page_urls(self, subscription):
        # each account can be displayed several times but with different set of documents
        # take all urls for each subscription
        xpath = '//div[contains(text(), "RELEVES DE COMPTES")]/following-sibling::table//tr//div[contains(@class, "table")]//a[contains(text(), "%s")]'

        # Declare a set for _urls to prevent the same URL from being added twice
        urls = set()
        for url in self.doc.xpath(xpath % subscription.id):
            urls.add(Link().filter([url]))

        return urls

    @method
    class iter_documents(ListElement):
        item_xpath = '//tr[@title="Relevé"][@id]'

        class item(ItemElement):
            klass = Document

            obj_id = Format('%s_%s', Env('sub_id'), Regexp(Link('./td/a'), r"mettreUnCookie\('(\d+)'"))
            obj_label = CleanText('./th/span')
            obj_date = Date(CleanText('td[1]'), dayfirst=True)
            obj_url = Regexp(Link('./td/a'), r"ouvreTelechargement\('(.*?)'\)")
            obj_type = DocumentTypes.STATEMENT
            obj_format = 'pdf'
