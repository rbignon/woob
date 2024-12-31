# -*- coding: utf-8 -*-

# flake8: compatible

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

import json
import re

from dateutil.relativedelta import relativedelta

from woob.browser.elements import ItemElement, ListElement, SkipItem, method
from woob.browser.filters.html import AbsoluteLink, Link
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Currency, Date, Env, Field, Filter, Format, QueryValue,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Bill, Subscription
from woob.capabilities.profile import Profile
from woob.tools.date import parse_french_date


class ErrorPage(HTMLPage):
    pass


class FormatDate(Filter):
    def __init__(self, pattern, selector):
        super(FormatDate, self).__init__(selector)
        self.pattern = pattern

    def filter(self, _date):
        return _date.strftime(self.pattern)


class LoginPage(HTMLPage):
    def is_here(self):
        if 'text/html' not in self.response.headers.get('content-type', ''):
            return False
        if not self.doc.xpath('//input[@id="login-username"]'):
            return False
        return True

    def login(self, login, password):
        form = self.get_form('//form')
        form['login-username'] = login
        form['login-password'] = password
        form.submit()

    def get_error(self):
        return CleanText('//div[has-class("override:text-status-error")]')(self.doc)


class MainPage(LoggedPage, HTMLPage):
    is_here = '//div[has-class("table-facture")]'

    def get_information_message(self):
        return CleanText('//div[has-class("flash")]')(self.doc)

    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@id="table-invoice"]//div[has-class("invoice")]'

        def store(self, obj):
            # This code enables doc_id when there
            # are several docs with the exact same id
            # sometimes we have two docs on the same date
            _id = obj.id
            n = 1
            while _id in self.objects:
                n += 1
                _id = '%s-%s' % (obj.id, n)
            obj.id = _id
            self.objects[obj.id] = obj
            return obj

        class item(ItemElement):
            klass = Bill

            obj_url = AbsoluteLink('.//a[@data-title="Télécharger ma facture"]')
            obj_total_price = CleanDecimal.SI('.//div[has-class("table-price")]')
            obj_currency = Currency('.//div[has-class("table-price")]')
            obj_format = 'pdf'
            obj__raw_date = QueryValue(Field('url'), 'date')

            def obj__date_recap(self):
                # Unfortunately the date of those 'recap' documents is lost (not
                # present in url, etc...) and is only available in the PDFs
                # themselves.
                # Arbitrarily, we set it to the last day of month.
                dt = Date(
                    Format("1 %s", CleanText('.//div[has-class("date")]')),
                    parse_func=parse_french_date,
                    dayfirst=True,
                )(self)
                dt += relativedelta(months=1, days=-1)
                return dt

            def obj_id(self):
                if ("pdfrecap" in Field("url")(self)) != Env("is_recapitulatif")(self):
                    raise SkipItem()
                if Env("is_recapitulatif")(self):
                    return Format(
                        "%s_%s", Env("sub"), FormatDate("%Y%m", Field("_date_recap"))
                    )(self)
                return Format("%s_%s", Env("sub"), Field("_raw_date"))(self)

            def obj_label(self):
                if Env("is_recapitulatif")(self):
                    return Format(
                        "Multiligne - %s", CleanText('.//div[has-class("date")]')
                    )(self)
                return Format(
                    "%s - %s",
                    CleanText(
                        '//div[@class="table-container"]/p[@class="table-sub-title"]'
                    ),
                    CleanText('.//div[has-class("date")]'),
                )(self)

            def obj_date(self):
                if Env("is_recapitulatif")(self):
                    return Field("_date_recap")(self)
                return Date(Field("_raw_date"))(self)


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Profile

        obj_id = CleanText('//div[contains(text(), "Mon adresse email")]/..', children=False)
        obj_email = Field('id')
        obj_name = CleanText('//div[contains(text(), "Titulaire")]/..', children=False)
        obj_phone = CleanText(
            '//div[@class="current-user__infos"]/div[contains(text(), "Ligne")]/span',
            replace=[(" ", "")],
        )

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_full_address = Env('full_address', default=NotAvailable)
            obj_street = Env('street', default=NotAvailable)
            obj_postal_code = Env('postal_code', default=NotAvailable)
            obj_city = Env('city', default=NotAvailable)

            def parse(self, obj):
                full_address = CleanText('//address')(self)
                self.env['full_address'] = full_address
                m = re.search(r'(\d{1,4}.*) (\d{5}) (.*)', full_address)
                if m:
                    street, postal_code, city = m.groups()
                    self.env['street'] = street
                    self.env['postal_code'] = postal_code
                    self.env['city'] = city


class PdfPage(RawPage):
    pass


class OfferPage(LoggedPage, HTMLPage):
    def fill_subscription(self, subscription):
        subscription._is_recapitulatif = False
        subscription._real_id = subscription.id
        offer_name = CleanText('//div[@class="title"]')(self.doc)
        if offer_name:
            subscription.label = "%s - %s" % (subscription._phone_number, offer_name)

    def get_first_subscription_id(self):
        """Return the first subscription id if available."""
        return QueryValue(
            Link(
                '//div[@class="list-users"]/ul[@id="multi-ligne-selector"]'
                + '/li/ul/li[1]/a',
                default=None,
            ),
            'switch-user',
            default=None,
        )(self.doc)

    @method
    class get_first_subscription(ItemElement):
        klass = Subscription

        obj_id = CleanText('.//div[contains(text(), "Identifiant")]/span')
        obj__phone_number = CleanText('//div[@class="current-user__infos"]/div[3]/span', replace=[(' ', '')])
        obj_subscriber = CleanText('//div[@class="current-user__infos"]/div[has-class("identite")]')
        obj_label = Field('id')

    @method
    class iter_next_subscription(ListElement):
        item_xpath = '//div[@class="list-users"]/ul[@id="multi-ligne-selector"]/li/ul/li[has-class("user")][position()>1]/a'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(QueryValue(AbsoluteLink('.'), 'switch-user'))
            obj__phone_number = CleanText('.//span[has-class("msidn")]', replace=[(" ", "")])
            obj_subscriber = CleanText('.//span[has-class("name-bold")]')
            obj_label = Field('id')


class OptionsPage(LoggedPage, HTMLPage):
    def get_api_key(self):
        api_key = self.doc.xpath('//div[has-class("page")]//div[@id="opt_secret-key"]')
        if api_key:
            return api_key[0].text.strip()
        else:
            return None


class CsrfPage(JsonPage):
    def get_token(self):
        return Dict('csrfToken')(self.doc)


class ProvidersPage(JsonPage):
    def get_auth_provider(self):
        return Dict('credentials')(self.doc)


class CredentialsPage(JsonPage):
    def get_error(self):
        return QueryValue(Dict('url'), 'error', default=None)(self.doc)


class SessionPage(JsonPage):
    def get_token(self):
        return Dict('user/token')(self.doc)

    def get_2fa_type(self):
        return Dict('user/type2FA', default=None)(self.doc)

    def get_otp_id(self):
        return Dict('user/otpId', default=None)(self.doc)


class RSCPage(JsonPage):
    """
    This is a React Server Component partial page.

    The content of the page is a list of (JSON) representation of a
    tree of components/html or metadata such as required imports,
    etc... that needs to be loaded / updated.
    Each JSON line is preceded by an identifier and ':'.
    Sometimes, the ':' can be followed by another character (often 'I').

    We extract this into a dict of (rowid, JSON line).

    The identifier (rowid) is related to the page structure, and so is stable
    (as long as the page structure is stable), thus we can query it to
    retrieve information about which component needs to be updated.

    Here, it's mainly used to get the error messages sent by the server.
    """
    def is_here(self):
        if 'text/x-component' not in self.response.headers.get('content-type', ''):
            return False
        return True

    def build_doc(self, text: str) -> Dict:
        forbidden_extra_chars = re.compile(r'\{|\[|n|\d')
        result = {}
        for line in text.splitlines():
            if line.strip() == '':
                continue
            (rowID, sep, row) = line.partition(':')
            mtch = forbidden_extra_chars.match(row[0])
            if mtch is None:
                rowID += row[0]
                row = row[1:]
            result[rowID] = json.loads(row)
        return result


class LoginRSCPage(RSCPage):
    """
    The React Server Component update of the main Login page.

    Of interest is the entry named `2:`, which seems to contain an error message:
    ```
    0:[...]
    ...
    1:null
    ...
    2:["$","$L4",null,{"header":"Bienvenue","description":"Saisissez les identifiants de votre Espace Abonné mobile","errorMessage":"Suite à plusieurs tentatives, votre compte a été temporairement bloqué. Veuillez réessayer dans 13 minutes.","................]
    ```

    So:
    * Dict('2') retrives this JSON line,
    * out_row[3] retrieves the 3rd element of the JSON array - a dict object `{"header":"Bienvenue","description":"Saisissez les identifiants.....`
    * this dict object has an entry `errorMessage` which is either `$undefined` or a message.
    """
    def get_error(self):
        result = None
        our_row = Dict('2')(self.doc)
        if our_row:
            try:
                result = our_row[3].get('errorMessage', None)
            except IndexError:
                pass
        return result


class OtpPage(RSCPage):
    """
    The React Server Component update of the Otp Email Page.

    Of interest is the entry named `1:`, which is the new OtpIp
    ```
    0:["$@1",["ABCDEF0123456789ABCDEF",null]]
    1:12345678
    ```

    So:
    * Dict('1') retrives this JSON line.
    """
    def get_otp_id(self):
        result = None
        our_row = Dict('1')(self.doc)
        if our_row:
            result = our_row
        return result
