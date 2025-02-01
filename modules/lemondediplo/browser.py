# -*- coding: utf-8 -*-

# Copyright(C) 2021      Bezleputh
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


from woob.browser import URL, LoginBrowser, need_login
from woob.exceptions import BrowserIncorrectPassword

from .pages import ArticlesPage, BlogsPage, LoginErrorPage, LoginPage


class LemondediploBrowser(LoginBrowser):
    TIMEOUT = 30
    BASEURL = "https://www.monde-diplomatique.fr"
    BLOGURL = "https://blog.mondediplo.net"

    login_page = URL("/load_mon_compte", LoginPage)
    login_error = URL(rf"{BASEURL}\?erreur_connexion=.*", LoginErrorPage)

    articles_page = URL(r"/(?P<id>.+)", rf"{BASEURL}", ArticlesPage)
    blogs_page = URL(rf"{BLOGURL}/(?P<id>.+)", rf"{BLOGURL}", BlogsPage)

    def do_login(self):
        self.session.headers["X-Requested-With"] = "XMLHttpRequest"

        data = {"retour": self.BASEURL, "erreur_connexion": "", "triggerAjaxLoad": ""}
        self.login_page.go(data=data).login(self.username, self.password)

        if not self.page.logged or self.login_error.is_here():
            raise BrowserIncorrectPassword()

    @need_login
    def iter_threads(self):
        return self.articles_page.go().iter_threads()

    @need_login
    @articles_page.id2url
    def get_thread(self, url, obj=None):
        self.location(url)
        assert self.articles_page.is_here()
        obj = self.page.get_thread(obj=obj)
        obj.root = self.page.get_article()
        obj.root.thread = obj
        return obj

    @need_login
    def handle_archives(self, path):
        return self.articles_page.go(id=path.replace("-", "/")).iter_archive_threads()

    def iter_blog_threads(self):
        return self.blogs_page.go().iter_blog_thread()

    @blogs_page.id2url
    def get_blog_thread(self, url, obj=None):
        self.location(url)
        assert self.blogs_page.is_here()
        obj = self.page.get_thread(obj=obj)
        obj.root = self.page.get_article()
        obj.root.thread = obj
        return obj
