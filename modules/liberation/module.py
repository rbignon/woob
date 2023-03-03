# Copyright(C) 2013 Florent Fourcot
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

from woob.tools.newsfeed import Newsfeed
from woob.capabilities.messages import CapMessages, Thread
from woob.tools.backend import BackendConfig
from woob.tools.value import Value
from woob_modules.genericnewspaper.module import GenericNewspaperModule

from .browser import NewspaperLibeBrowser
from .tools import rssid, url2id


class NewspaperLibeModule(GenericNewspaperModule, CapMessages):
    MAINTAINER = 'Florent Fourcot'
    EMAIL = 'weboob@flo.fourcot.fr'
    VERSION = '3.3.1'
    DEPENDENCIES = ('genericnewspaper',)
    LICENSE = 'AGPLv3+'
    STORAGE = {'seen': {}}
    NAME = 'liberation'
    DESCRIPTION = 'Libération newspaper website'
    BROWSER = NewspaperLibeBrowser
    RSSID = staticmethod(rssid)
    URL2ID = staticmethod(url2id)
    RSSSIZE = 30

    CONFIG = BackendConfig(
        Value(
            'feed',
            label='RSS feed',
            choices={
                '9': u'A la une sur Libération',
                '10': u'Monde',
                '11': u'Politiques',
                '12': u'Société',
                '13': u'Économie',
                '14': u'Sports',
                '17': u'Labo: audio, vidéo, diapos, podcasts',
                '18': u'Rebonds',
                '44': u'Les chroniques de Libération',
                '53': u'Écrans',
                '54': u'Next',
                '58': u'Cinéma'
            }
        )
    )

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.RSS_FEED = f'http://www.liberation.fr/rss/{self.config["feed"].get()}'

    def iter_threads(self):
        for article in Newsfeed(self.RSS_FEED, self.RSSID).iter_entries():
            thread = Thread(article.id)
            thread.title = article.title
            thread.date = article.datetime
            yield thread
