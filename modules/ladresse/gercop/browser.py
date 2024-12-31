# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

from woob.browser.browsers import LoginBrowser, StatesMixin, need_login
from woob.browser.exceptions import ClientError
from woob.browser.url import URL
from woob.exceptions import BrowserIncorrectPassword, BrowserPasswordExpired

from .pages import (
    AuthenticatePage, DocumentCategoriesPage, DocumentsPage, HomePage, LoginPage, PasswordExpiredPage, ProfilePage,
)


__all__ = ['GercopBrowser']


class GercopBrowser(LoginBrowser, StatesMixin):
    login = URL(r'connexion/', LoginPage)
    home = URL(r'extranet$', HomePage)
    password_expired = URL(r'password-expiration', PasswordExpiredPage)

    authenticate = URL(r'authenticate', AuthenticatePage)
    profile = URL(r'extranet/locataire$', ProfilePage)
    document_categories = URL(
        r'extranet/locataire/documents/classeur/$',
        DocumentCategoriesPage,
    )
    documents = URL(
        r'extranet/locataire/documents/classeur/(?P<category_id>\d+)',
        DocumentsPage,
    )
    document = URL(r'extranet/documents/download/(?P<document_id>\d+)')

    def __init__(self, baseurl, *args, **kwargs):
        self.BASEURL = baseurl
        super().__init__(*args, **kwargs)

    def do_login(self):
        self.login.go()

        try:
            page = self.authenticate.open(json={
                'login': self.username,
                'password': self.password,
                'password_confirmation_validation': False,
                'password_strenght_validation': False,
            })
        except ClientError as exc:
            page = AuthenticatePage(self, exc.response)

        result = page.get_authentication_result()
        if not result['authentication']:
            raise BrowserIncorrectPassword(result['message'])

        self.home.go()
        if self.password_expired.is_here():
            raise BrowserPasswordExpired(self.page.get_error_message())

    @need_login
    def iter_documents(self):
        self.document_categories.go()
        for category in self.page.iter_categories():
            if category['fileCount'] == 0:
                continue

            self.documents.go(
                category_id=category['id'],
                params={
                    'itemCountPerPage': 100,
                    'currentPageNumber': 1,
                },
            )

            yield from self.page.iter_documents()

    @need_login
    def download_document(self, document):
        return self.open(self.document.build(document_id=document.id)).content

    @need_login
    def get_profile(self):
        page = self.profile.open()
        return page.get_profile()
