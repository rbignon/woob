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
from woob.browser.pages import HTMLPage, LoggedPage, FormNotFound, PartialHTMLPage, pagination
from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Link, Attr
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Env, Regexp, Format, RawText,
    Field, Currency, Date, Async, AsyncLoad,
    Coalesce,
)
from woob.capabilities.bill import DocumentTypes, Bill, Subscription
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


class ResetPasswordPage(HTMLPage):
    def get_message(self):
        return CleanText('//h2')(self.doc)


class LanguagePage(HTMLPage):
    pass


class LoginPage(PartialHTMLPage):
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

    def has_captcha(self):
        return self.doc.xpath('//div[@id="image-captcha-section"]//img[@id="auth-captcha-image"]/@src')

    def get_response_form(self):
        try:
            form = self.get_form(id='auth-mfa-form')
            return form
        except FormNotFound:
            form = self.get_form(nr=0)
            return form

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
    class iter_documents(ListElement):
        item_xpath = '//div[contains(@class, "order") and contains(@class, "a-box-group")]'

        def next_page(self):
            return Link('//ul[@class="a-pagination"]/li[@class="a-last"]/a')(self)

        class item(ItemElement):
            klass = Bill
            load_details = Field('_pre_url') & AsyncLoad

            obj__simple_id = Coalesce(
                CleanText('.//span[contains(text(), "N° de commande")]/following-sibling::span', default=NotAvailable),
                CleanText('.//span[contains(text(), "Order")]/following-sibling::span'),
            )

            obj_id = Format('%s_%s', Env('subid'), Field('_simple_id'))

            obj__pre_url = Format('/gp/shared-cs/ajax/invoice/invoice.html?orderId=%s&relatedRequestId=%s&isADriveSubscription=&isHFC=',
                                  Field('_simple_id'), Env('request_id'))
            obj_label = Format('Facture %s', Field('_simple_id'))
            obj_type = DocumentTypes.BILL

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

            def obj_url(self):
                async_page = Async('details').loaded_page(self)
                url = Coalesce(
                    Link('//a[@class="a-link-normal" and contains(text(), "Invoice")]', default=NotAvailable),
                    Link('//a[contains(text(), "Order Details")]', default=NotAvailable),
                    default=NotAvailable,
                )(self)
                if not url:
                    download_elements = async_page.doc.xpath('//a[contains(@href, "download")]')
                    if download_elements and len(download_elements) > 1:
                        # Sometimes there are multiple invoices for one order and to avoid missing the other invoices
                        # we are taking the order summary instead
                        url = Link(
                            '//a[contains(text(), "Récapitulatif de commande")]',
                            default=NotAvailable
                        )(async_page.doc)
                    else:
                        url = Coalesce(
                            Link(
                                '//a[contains(@href, "download")]|//a[contains(@href, "generated_invoices")]',
                                default=NotAvailable,
                            ),
                            Link('//a[contains(text(), "Récapitulatif de commande")]', default=NotAvailable),
                            default=NotAvailable
                        )(async_page.doc)
                doc_id = Field('id')(self)
                # We have to check whether the document is available or not and we have to keep the content to use
                # it later in obj_format to determine if this document is a PDF. We can't verify this information
                # with a HEAD request since Amazon doesn't allow those requests (405 Method Not Allowed)
                if 'summary' in url and not self.page.browser.summary_documents_content.get(doc_id, None):
                    try:
                        self.page.browser.summary_documents_content[doc_id] = self.page.browser.open(url).content
                    except ServerError:
                        # For some orders (witnessed for 1 order right now) amazon respond with a status code 500
                        # It's also happening using a real browser
                        return NotAvailable
                return url

            def obj_format(self):
                url = Field('url')(self)
                if not url:
                    return NotAvailable
                if 'summary' in url:
                    content = self.page.browser.summary_documents_content[Field('id')(self)]
                    # Summary documents can be a PDF file or an HTML file but there are
                    # no hints of it before trying to get the document
                    if content[:4] != b'%PDF':
                        return 'html'
                return 'pdf'

            def condition(self):
                # Sometimes an order can be empty
                return bool(Coalesce(
                    CleanText('.//div[has-class("a-span4")]'),
                    CleanText('.//div[has-class("a-span3")]'),
                    CleanText('.//div[has-class("a-span2")]'),
                    default=NotAvailable,
                )(self))


class DownloadDocumentPage(LoggedPage, PartialHTMLPage):
    pass
