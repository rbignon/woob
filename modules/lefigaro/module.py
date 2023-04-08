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

from woob.tools.newsfeed import Newsfeed
from woob.tools.backend import BackendConfig
from woob.tools.value import Value
from woob.capabilities.messages import CapMessages, Thread
from woob_modules.genericnewspaper.module import GenericNewspaperModule

from .browser import NewspaperFigaroBrowser
from .tools import rssid


class NewspaperFigaroModule(GenericNewspaperModule, CapMessages):
    MAINTAINER = 'Julien Hebert'
    EMAIL = 'juke@free.fr'
    VERSION = '3.5'
    DEPENDENCIES = ('genericnewspaper',)
    LICENSE = 'AGPLv3+'
    STORAGE = {'seen': {}}
    NAME = 'lefigaro'
    DESCRIPTION = 'Le Figaro French newspaper website'
    BROWSER = NewspaperFigaroBrowser
    RSS_FEED = 'http://rss.lefigaro.fr/lefigaro/laune?format=xml'
    RSSID = staticmethod(rssid)
    RSSSIZE = 30
    CONFIG = BackendConfig(
        Value(
            'feed',
            label='RSS feed',
            choices={
                'actualites': 'actualites',
                'flash-actu': 'flash-actu',
                'politique': 'politique',
                'international': 'international',
                'actualite-france': 'actualite-france',
                'hightech': 'hightech',
                'sciences': 'sciences',
                'sante': 'sante',
                'lefigaromagazine': 'lefigaromagazine',
                'photos': 'photos',
                'economie': 'economie',
                'societes': 'societes',
                'medias': 'medias',
                'immobilier': 'immobilier',
                'assurance': 'assurance',
                'retraite': 'retraite',
                'placement': 'placement',
                'impots': 'impots',
                'conso': 'conso',
                'emploi': 'emploi',
                'culture': 'culture',
                'cinema': 'cinema',
                'musique': 'musique',
                'livres': 'livres',
                'theatre': 'theatre',
                'lifestyle': 'lifestyle',
                'automobile': 'automobile',
                'gastronomie': 'gastronomie',
                'horlogerie': 'horlogerie',
                'mode-homme': 'mode-homme',
                'sortir-paris': 'sortir-paris',
                'vins': 'vins',
                'voyages': 'voyages',
                'sport': 'sport',
                'football': 'football',
                'rugby': 'rugby',
                'tennis': 'tennis',
                'cyclisme': 'cyclisme',
                'sport-business': 'sport-business'
            }
        )
    )

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.RSS_FEED = "http://www.lefigaro.fr/rss/figaro_%s.xml" % self.config['feed'].get()

    def iter_threads(self):
        for article in Newsfeed(self.RSS_FEED, self.RSSID).iter_entries():
            thread = Thread(article.id)
            thread.title = article.title
            thread.date = article.datetime
            yield thread
