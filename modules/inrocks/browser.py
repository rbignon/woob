# Copyright(C) 2011  Julien Hebert
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

from woob.browser.url import URL
from woob_modules.genericnewspaper.browser import GenericNewspaperBrowser

from .pages import ArticlePage


class NewspaperInrocksBrowser(GenericNewspaperBrowser):
    BASEURL = 'http://www.lesinrocks.com'

    article = URL(
        r'/\?p=.+',
        r'/\d{4}/\d{2}/\d{2}/actualite/.*',
        r'http://blogs.lesinrocks.com/.*',
        r'/.*',
        ArticlePage
    )
