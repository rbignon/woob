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

from woob.browser import URL, need_login
from woob_modules.materielnet.browser import MaterielnetBrowser
from woob_modules.materielnet.pages import PeriodPage

from .pages import (
    ParDocumentDetailsPage, ParDocumentsPage, ParLoginPage,
    ProDocumentsPage, ProfilePage, ProProfilePage,
)


class MyURL(URL):
    def go(self, *args, **kwargs):
        kwargs['lang'] = self.browser.lang
        return super().go(*args, **kwargs)


class LdlcParBrowser(MaterielnetBrowser):
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


class LdlcProBrowser(LdlcParBrowser):
    BASEURL = 'https://secure.ldlc.pro'

    profile = LdlcParBrowser.profile.with_page(ProProfilePage)
    documents = LdlcParBrowser.documents.with_page(ProDocumentsPage)
