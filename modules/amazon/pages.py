# -*- coding: utf-8 -*-

# Copyright(C) 2017      Théo Dorée
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

from woob.browser.exceptions import ServerError
from woob.browser.pages import HTMLPage, LoggedPage, FormNotFound, PartialHTMLPage, pagination, JsonPage
from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Link, Attr, HasElement
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Env, Regexp, Format, RawText,
    Field, Currency, Date, Coalesce,
)
from woob.capabilities.bill import Bill, Subscription
from woob.capabilities.base import NotAvailable
from woob.tools.json import json
from woob.tools.date import parse_french_date


class HomePage(HTMLPage):
    def get_login_link(self):
        return Attr('//a[@data-nav-role="signin"]', 'href')(self.doc)

    def get_panel_link(self):
        return Link('//a[contains(@href, "homepage.html") and has-class(@nav-link)]')(self.doc)


class SecurityPage(HTMLPage):
    def get_otp_type(self):
        if self.doc.xpath('//form[@id="auth-select-device-form"]'):
            return 'auth-select-device-form'
        # amazon send us otp in two cases:
        # - if it's the first time we connect to this account for an ip => manage it normally
        # - if user has activated otp in his options => raise ActionNeeded, an ask user to deactivate it
        form = self.get_form(xpath='//form[.//h1]')
        url = form.url.replace(self.browser.BASEURL, '')

        # verify: this otp is sent by amazon when we connect to the account for the first time from a new ip or computer
        # /ap/signin: this otp is a user activated otp which is always present
        assert url in ('verify', '/ap/signin'), url
        return url

    def get_otp_message(self):
        return CleanText('//div[@class="a-box-inner"]/p')(self.doc)

    def send_code(self):
        form = self.get_form()
        if form.el.attrib.get('id') == 'auth-select-device-form':
            # the first is sms, second email, third application
            # the first item is automatically selected
            form.submit()

        if form.el.attrib.get('id') == 'auth-mfa-form':
            # when code is sent by sms, server send it automatically, nothing to do here
            return

        if 'sms' in self.doc.xpath('//div[@data-a-input-name="option"]//input[@name="option"]/@value'):
            form['option'] = 'sms'

        # by email, we have to confirm code sending
        form.submit()

    def get_response_form(self):
        try:
            form = self.get_form(id='auth-mfa-form')
            return {'form': form, 'style': 'userDFA'}
        except FormNotFound:
            form = self.get_form(nr=0)
            return {'form': form, 'style': 'amazonDFA'}

    def get_captcha_url(self):
        return Attr('//img[@alt="captcha"]', 'src', default=NotAvailable)(self.doc)

    def resolve_captcha(self, captcha_response):
        form = self.get_form('//form[@action="verify"]')
        form['cvf_captcha_input'] = captcha_response
        form.submit()

    def has_form_verify(self):
        return bool(self.doc.xpath('//form[@action="verify"]'))

    def has_form_auth_mfa(self):
        return bool(self.doc.xpath('//form[@id="auth-mfa-form"]'))

    def has_form_select_device(self):
        return bool(self.doc.xpath('//form[@id="auth-select-device-form"]'))


class ApprovalPage(HTMLPage):
    def get_msg_app_validation(self):
        msg = CleanText('//div[has-class("a-spacing-large")]/span[has-class("transaction-approval-word-break")]')
        sending_address = CleanText('//div[@class="a-row"][1]')
        return Format('%s %s', msg, sending_address)(self.doc)

    def get_link_app_validation(self):
        return Attr('//input[@name="openid.return_to"]', 'value')(self.doc)

    def resend_link(self):
        form = self.get_form(id='resend-approval-form')
        form.submit()

    def get_polling_request(self):
        form = self.get_form(id="pollingForm")
        return form.request


class PollingPage(HTMLPage):
    def get_approval_status(self):
        return Attr('//input[@name="transactionApprovalStatus"]', 'value', default=None)(self.doc)


class CountriesPage(JsonPage):
    def get_csrf_token(self):
        return Dict('data/inputs/token')(self.doc)


class LanguagePage(HTMLPage):
    pass


class AccountSwitcherLoadingPage(HTMLPage):
    def is_here(self):
        return bool(self.doc.xpath('//div[@id="ap-account-switcher-container"]'))

    def get_arb_token(self):
        # Get the token from attribute data-arbToken (data-arbtoken using the Attr filter)
        return Attr('//div[@id="ap-account-switcher-container"]', 'data-arbtoken')(self.doc)


class AccountSwitcherPage(PartialHTMLPage):
    def validate_account(self):
        form = self.get_form(xpath='//form[@action="/ap/switchaccount"]')
        form['switch_account_request'] = Attr('//a[@data-name="switch_account_request"]', 'data-value')(self.doc)
        form.submit()

    def get_add_account_link(self):
        return Link('//a[@id="cvf-account-switcher-add-accounts-link"]')(self.doc)

    def has_account_to_switch_to(self):
        return HasElement('//form[@action="/ap/switchaccount"]')(self.doc)


class SwitchedAccountPage(JsonPage):
    def get_redirect_url(self):
        return Dict('redirectUrl')(self.doc)


class LoginPage(PartialHTMLPage):
    def is_here(self):
        return not bool(self.doc.xpath('//div[@id="ap-account-switcher-container"]'))

    ENCODING = 'utf-8'

    def login(self, login, password, captcha=None):
        form = self.get_form(name='signIn')

        form['email'] = login
        form['password'] = password
        form['rememberMe'] = "true"

        if captcha:
            form['guess'] = captcha
        # we catch redirect to check if the browser send a notification for the user
        form.submit(allow_redirects=False)

    def get_captcha(self):
        return Attr('//img[@id="auth-captcha-image"]', 'src', default=None)(self.doc)

    def get_sign_in_form(self):
        return self.get_form(name='signIn')

    def get_error_message(self):
        return Coalesce(
            CleanText('//div[@id="auth-error-message-box"]'),
            CleanText('//div[not(@id="auth-cookie-warning-message")]/div/h4[@class="a-alert-heading"]'),
            default=NotAvailable,
        )(self.doc)


class PasswordExpired(HTMLPage):
    def get_message(self):
        return CleanText('//form//h2')(self.doc)


class SubscriptionsPage(LoggedPage, HTMLPage):
    @method
    class get_item(ItemElement):
        klass = Subscription

        obj_id = 'amazon'

        def obj_subscriber(self):
            completed_customer_profile_data = Regexp(
                RawText('//script[contains(text(), "window.CustomerProfileRootProps")]'),
                r'window.CustomerProfileRootProps = ({.+});',
                default=NotAvailable,
            )(self)
            if completed_customer_profile_data:
                profile_data = json.loads(completed_customer_profile_data)
                return profile_data.get('nameHeaderData', {}).get('name', NotAvailable)
            # The user didn't complete his profile, so we have to get the data in a different way
            # We have to get the name from "Cette action est nécessaire, cependant vous pouvez saisir
            # un nom différent de celui associé à votre compte (<fullname>)" (The message change with
            # a different language but the regex stays the same)
            return Regexp(
                CleanText('//div[@data-name="name"]//div[@class="a-row"]/span'),
                r'.*\((.*)\)',
                default=NotAvailable,
            )(self)

        def obj_label(self):
            return self.page.browser.username


class HistoryPage(LoggedPage, HTMLPage):
    def get_b2b_group_key(self):
        return Attr(
            '//select[@name="selectedB2BGroupKey"]/option[contains(text(), "Afficher toutes les commandes")]',
            'value',
            default=None
        )(self.doc)


class DocumentsPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_summary_documents(ListElement):
        item_xpath = '//div[contains(@class, "order") and contains(@class, "a-box-group")]'

        def next_page(self):
            return Link('//ul[@class="a-pagination"]/li[@class="a-last"]/a')(self)

        class item(ItemElement):
            klass = Bill

            obj__order_id = Coalesce(
                CleanText('.//span[contains(text(), "N° de commande")]/following-sibling::span', default=NotAvailable),
                CleanText('.//span[contains(text(), "Order")]/following-sibling::span'),
            )
            obj_id = Format('%s_%s', Env('subid'), Field('_order_id'))
            obj_label = Format('Récapitulatif de commande %s', Field('_order_id'))

            def obj_date(self):
                # The date xpath changes depending on the kind of order
                return Coalesce(
                    Date(CleanText('.//div[has-class("a-span4") and not(has-class("recipient"))]/div[2]'), parse_func=parse_french_date, dayfirst=True, default=NotAvailable),
                    Date(CleanText('.//div[has-class("a-span3") and not(has-class("recipient"))]/div[2]'), parse_func=parse_french_date, dayfirst=True, default=NotAvailable),
                    Date(CleanText('.//div[has-class("a-span2") and not(has-class("recipient"))]/div[2]'), parse_func=parse_french_date, dayfirst=True, default=NotAvailable),
                    default=NotAvailable,
                )(self)

            def obj_total_price(self):
                # Some orders, audiobooks for example, are paid using "audio credits", they have no price or currency
                currency = Env('currency')(self)
                return CleanDecimal(
                    './/div[has-class("a-col-left")]//span[has-class("value") and contains(., "%s")]' % currency,
                    replace_dots=currency == 'EUR', default=NotAvailable
                )(self)

            def obj_currency(self):
                currency = Env('currency')(self)
                return Currency(
                    './/div[has-class("a-col-left")]//span[has-class("value") and contains(., "%s")]' % currency,
                    default=NotAvailable
                )(self)

            def condition(self):
                # Sometimes an order can be empty
                return bool(Coalesce(
                    CleanText('.//div[has-class("a-span4")]'),
                    CleanText('.//div[has-class("a-span3")]'),
                    CleanText('.//div[has-class("a-span2")]'),
                    default=NotAvailable,
                )(self))


class InvoiceFilesListPage(LoggedPage, PartialHTMLPage):
    def is_missing_some_invoices(self):
        return HasElement(
            '//a[contains(text(), "Invoice unavailable for some items")]|'
            + '//a[contains(text(), "Pas de facture disponible pour certains articles")]'
        )(self.doc)

    @method
    class iter_invoice_documents(ListElement):
        item_xpath = '//a[contains(text(), "Facture")]|//a[contains(text(), "Invoice")]'

        class item(ItemElement):
            klass = Bill

            obj_id = Format('%s-%s', Env('summary_doc_id'), Field('_file_number'))
            obj__file_number = Regexp(
                CleanText('.'),
                r'^(?:Facture(?: ou note de crédit)?|Invoice(?: or Credit note)?) (\d+)$',
                default=NotAvailable
            )
            obj__file_label = Regexp(
                CleanText('.'),
                r'^((?:Facture(?: ou note de crédit)?|Invoice(?: or Credit note)?)) \d+$',
            )
            obj_date = Env('date')
            # Will result to "Invoice 123-4567891-2345678-1" or "Invoice or Credit note 123-4567891-2345678-1"
            obj_label = Format('%s %s-%s', Field('_file_label'), Env('order_id'), Field('_file_number'))
            obj_url = Link('.')
            obj_format = 'pdf'

            def condition(self):
                return Field('_file_number')(self) != NotAvailable

    @method
    class fill_order_document(ItemElement):
        # Will result to "Order Summary 123-4567891-2345678" (and in french for the french website)
        obj_label = Format(
            '%s %s',
            CleanText('//a[contains(text(), "Récapitulatif de commande")]|//a[contains(text(), "Order Summary")]'),
            Env('order_id')
        )

        def obj_url(self):
            order_summary_link = Link(
                '//a[contains(text(), "Récapitulatif de commande")]|//a[contains(text(), "Order Summary")]',
                default=NotAvailable
            )(self)
            # We have to check whether the document is available or not and we have to keep the content to use
            # it later in obj_format to determine if this document is a PDF. We can't verify this information
            # with a HEAD request since Amazon doesn't allow those requests (405 Method Not Allowed)
            if order_summary_link:
                try:
                    self.page.get_or_fetch_summary_content(self.obj.id, order_summary_link)
                except ServerError:
                    # For some orders (witnessed for 1 order right now) amazon respond with a status code 500
                    # It's also happening using a real browser
                    return NotAvailable
            return order_summary_link

        def obj_format(self):
            url = Field('url')(self)
            if not url:
                return NotAvailable

            content = self.page.get_or_fetch_summary_content(self.obj.id, url)
            # Summary documents can be a PDF file (seems to be rare) or an
            # HTML file but there are no hints of it before trying to get the
            # document
            if content[:4] != b'%PDF':
                return 'html'

            # Log those cases to check if they're still occurring
            self.logger.warning('The summary document is a PDF instead instead of an HTML page')
            return 'pdf'

    def get_or_fetch_summary_content(self, doc_id, url):
        if not self.browser.summary_documents_content.get(doc_id):
            self.browser.summary_documents_content[doc_id] = self.browser.open(url).content

        return self.browser.summary_documents_content[doc_id]
