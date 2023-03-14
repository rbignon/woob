# Copyright(C) 2015      Vincent Paredes
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

from woob.browser import AbstractBrowser, LoginBrowser, URL, need_login
from woob.capabilities.captcha import RecaptchaV2Question
from woob.exceptions import BrowserIncorrectPassword

from .pages import (
    ParDocumentDetailsPage, ParDocumentsPage, ParLoginPage, PeriodPage,
    ProDocumentsPage, ProHomePage, ProLoginPage, ProfilePage
)


class MyURL(URL):
    def go(self, *args, **kwargs):
        kwargs['lang'] = self.browser.lang
        return super().go(*args, **kwargs)


class LdlcParBrowser(AbstractBrowser):
    PARENT = 'materielnet'
    BASEURL = 'https://secure2.ldlc.com'

    profile = MyURL(r'/(?P<lang>.*/)Account', ProfilePage)
    login = MyURL(r'/(?P<lang>.*/)Login/Login', ParLoginPage)

    documents = MyURL(r'/(?P<lang>.*/)Orders/PartialCompletedOrdersHeader', ParDocumentsPage)
    document_details = MyURL(r'/(?P<lang>.*/)Orders/PartialCompletedOrderContent', ParDocumentDetailsPage)
    periods = MyURL(r'/(?P<lang>.*/)Orders/CompletedOrdersPeriodSelection', PeriodPage)

    def __init__(self, config, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.lang = 'fr-fr/'

    @need_login
    def iter_documents(self):
        for document in super().iter_documents():
            data = {'X-Requested-With': 'XMLHttpRequest'}
            self.location(document._detail_url, data=data)
            self.page.fill_document(obj=document)
            yield document


class LdlcProBrowser(LoginBrowser):
    BASEURL = 'https://secure.ldlc-pro.com'

    login = URL(r'/Account/LoginPage.aspx', ProLoginPage)
    bills = URL(r'/Account/CommandListingPage.aspx', ProDocumentsPage)
    home = URL(r'/default.aspx$', ProHomePage)

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config

    def do_login(self):
        self.login.stay_or_go()
        sitekey = self.page.get_recaptcha_sitekey()
        if sitekey and not self.config['captcha_response'].get():
            raise RecaptchaV2Question(website_key=sitekey, website_url=self.login.build())

        self.page.login(self.username, self.password, self.config['captcha_response'].get())

        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())

    @need_login
    def get_subscription_list(self):
        return self.home.stay_or_go().get_subscriptions()

    @need_login
    def iter_documents(self):
        self.bills.go()
        hidden_field = self.page.get_ctl00_actScriptManager_HiddenField()

        for value in self.page.get_range():
            data = {
                'ctl00$cphMainContent$ddlDate': value,
                'ctl00$actScriptManager': 'ctl00$cphMainContent$ddlDate',
                '__EVENTTARGET': 'ctl00$cphMainContent$ddlDate',  # order them by date, very important for download
                'ctl00$cphMainContent$hfTypeTri': 1,
            }
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
                'x-microsoftajax': 'Delta=true',  # without it, it can return 500 (sometimes)
            }
            self.bills.go(data=data, headers=headers)
            view_state = self.page.get_view_state()
            # we need position to download file
            position = 1
            for bill in self.page.iter_documents():
                bill._position = position
                bill._view_state = view_state
                bill._hidden_field = hidden_field
                position += 1
                yield bill

    @need_login
    def download_document(self, bill):
        data = {
            '__EVENTARGUMENT': '',
            '__EVENTTARGET': '',
            '__LASTFOCUS': '',
            '__SCROLLPOSITIONX': 0,
            '__SCROLLPOSITIONY': 0,
            '__VIEWSTATE': bill._view_state,
            'ctl00$actScriptManager': '',
            'ctl00$cphMainContent$DetailCommand$hfCommand': '',
            'ctl00$cphMainContent$DetailCommand$txtAltEmail': '',
            'ctl00$cphMainContent$ddlDate': bill.date.year,
            'ctl00$cphMainContent$hfCancelCommandId': '',
            'ctl00$cphMainContent$hfCommandId': '',
            'ctl00$cphMainContent$hfCommandSearch': '',
            'ctl00$cphMainContent$hfOrderTri': 1,
            'ctl00$cphMainContent$hfTypeTri': 1,
            'ctl00$cphMainContent$rptCommand$ctl%s$hlFacture.x' % str(bill._position).zfill(2): '7',
            'ctl00$cphMainContent$rptCommand$ctl%s$hlFacture.y' % str(bill._position).zfill(2): '11',
            'ctl00$cphMainContent$txtCommandSearch': '',
            'ctl00$hfCountries': '',
            'ctl00$ucHeaderControl$ctrlSuggestedProductPopUp$HiddenCommandeSupplementaire': '',
            'ctl00$ucHeaderControl$ctrlSuggestedProductPopUp$hiddenPopUp': '',
            'ctl00$ucHeaderControl$txtSearch': 'Rechercher+...',
            'ctl00_actScriptManager_HiddenField': bill._hidden_field,
        }

        return self.open(bill.url, data=data).content
