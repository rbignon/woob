# * -*- coding: utf-8 -*-

# Copyright(C) 2011-2021  Johann Broudin
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


import re
import time
from datetime import datetime

from woob.capabilities.audio import BaseAudio, CapAudio
from woob.capabilities.audiostream import BaseAudioStream
from woob.capabilities.base import NotLoaded
from woob.capabilities.collection import CapCollection, Collection, CollectionNotFound
from woob.capabilities.radio import CapRadio, Radio
from woob.tools.backend import Module
from woob.tools.capabilities.streaminfo import StreamInfo

from .browser import RadioFranceBrowser


__all__ = ["RadioFranceModule"]


class RadioFranceModule(Module, CapRadio, CapCollection, CapAudio):
    NAME = "radiofrance"
    MAINTAINER = "Laurent Bachelier"
    EMAIL = "laurent@bachelier.name"
    VERSION = "3.7"
    DESCRIPTION = "Radios of Radio France: Inter, Info, Bleu, Culture, Musique, FIP, Le Mouv'"
    LICENSE = "AGPLv3+"
    BROWSER = RadioFranceBrowser

    _RADIOS = {
        "franceinter": {
            "title": "France Inter",
            "player": "",
            "live": "programmes?xmlHttpRequest=1",
            "podcast": "podcasts",
        },
        "franceculture": {
            "title": "France Culture",
            "player": "",
            "live": "programmes?xmlHttpRequest=1",
            "podcast": "programmes?xmlHttpRequest=1",
            "selection": "",
        },
        "francetvinfo": {
            "title": "France Info",
            "player": "en-direct/radio.html",
            "live": "",
            "podcast": "replay-radio",
            "selection": "en-direct/radio.html",
        },
        "fbidf": {"title": "France Bleu Île-de-France (Paris)", "player": "107-1", "live": "grid/107-1"},
        "fipradio": {
            "title": "FIP",
            "player": "player",
            "live": "import_si/si_titre_antenne/FIP_player_current",
            "selection": "%s" % int(time.mktime(datetime.utcnow().replace(hour=12, minute=0, second=0).timetuple())),
        },
        "francemusique": {
            "title": "France Musique",
            "player": "player",
            "live": "programmes?xmlHttpRequest=1",
            "podcast": "emissions",
        },
        "mouv": {
            "title": "Le Mouv'",
            "player": "player",
            "live": "lecteur_commun_json/timeline",
            "podcast": "podcasts",
            "selection": "lecteur_commun_json/reecoute-%s"
            % int(time.mktime(datetime.utcnow().replace(hour=13, minute=0, second=0).timetuple())),
        },
        "fbalsace": {"title": "France Bleu Alsace (Strasbourg)", "player": "alsace", "live": "grid/alsace"},
        "fbarmorique": {"title": "France Bleu Armorique (Rennes)", "player": "armorique", "live": "grid/armorique"},
        "fbauxerre": {"title": "France Bleu Auxerre", "player": "auxerre", "live": "grid/auxerre"},
        "fbazur": {"title": "France Bleu Azur (Nice)", "player": "azur", "live": "grid/azur"},
        "fbbearn": {"title": "France Bleu Bearn (Pau)", "player": "bearn", "live": "grid/bearn"},
        "fbbelfort": {
            "title": "France Bleu Belfort",
            "player": "belfort-montbeliard",
            "live": "grid/belfort-montbeliard",
        },
        "fbberry": {"title": "France Bleu Berry (Châteauroux)", "player": "berry", "live": "grid/berry"},
        "fbbesancon": {"title": "France Bleu Besancon", "player": "besancon", "live": "grid/besancon"},
        "fbbourgogne": {"title": "France Bleu Bourgogne (Dijon)", "player": "bourgogne", "live": "grid/bourgogne"},
        "fbbreihzizel": {
            "title": "France Bleu Breizh Izel (Quimper)",
            "player": "breizh-izel",
            "live": "grid/breizh-izel",
        },
        "fbchampagne": {
            "title": "France Bleu Champagne (Reims)",
            "player": "champagne-ardenne",
            "live": "grid/champagne-ardenne",
        },
        "fbcotentin": {"title": "France Bleu Cotentin (Cherbourg)", "player": "cotentin", "live": "grid/cotentin"},
        "fbcreuse": {"title": "France Bleu Creuse (Gueret)", "player": "creuse", "live": "grid/creuse"},
        "fbdromeardeche": {
            "title": "France Bleu Drome Ardeche (Valence)",
            "player": "drome-ardeche",
            "live": "grid/drome-ardeche",
        },
        "fbelsass": {"title": "France Bleu Elsass", "player": "elsass", "live": "grid/elsass"},
        "fbgardlozere": {
            "title": "France Bleu Gard Lozère (Nîmes)",
            "player": "gard-lozere",
            "live": "grid/gard-lozere",
        },
        "fbgascogne": {"title": "France Bleu Gascogne (Mont-de-Marsan)", "player": "gascogne", "live": "grid/gascogne"},
        "fbgironde": {"title": "France Bleu Gironde (Bordeaux)", "player": "gironde", "live": "grid/gironde"},
        "fbherault": {"title": "France Bleu Hérault (Montpellier)", "player": "herault", "live": "grid/herault"},
        "fbisere": {"title": "France Bleu Isère (Grenoble)", "player": "isere", "live": "grid/isere"},
        "fblarochelle": {"title": "France Bleu La Rochelle", "player": "la-rochelle", "live": "grid/la-rochelle"},
        "fblimousin": {"title": "France Bleu Limousin (Limoges)", "player": "limousin", "live": "grid/limousin"},
        "fbloireocean": {
            "title": "France Bleu Loire Océan (Nantes)",
            "player": "loire-ocean",
            "live": "grid/loire-ocean",
        },
        "fblorrainenord": {
            "title": "France Bleu Lorraine Nord (Metz)",
            "player": "lorraine-nord",
            "live": "grid/lorraine-nord",
        },
        "fbmaine": {"title": "France Bleu Maine", "player": "maine", "live": "grid/maine"},
        "fbmayenne": {"title": "France Bleu Mayenne (Laval)", "player": "mayenne", "live": "grid/mayenne"},
        "fbnord": {"title": "France Bleu Nord (Lille)", "player": "nord", "live": "grid/nord"},
        "fbcaen": {
            "title": "France Bleu Normandie (Calvados - Orne)",
            "player": "normandie-caen",
            "live": "grid/normandie-caen",
        },
        "fbrouen": {
            "title": "France Bleu Normandie (Seine-Maritime - Eure)",
            "player": "normandie-rouen",
            "live": "grid/normandie-rouen",
        },
        "fborleans": {"title": "France Bleu Orléans", "player": "orleans", "live": "grid/orleans"},
        "fbpaysbasque": {
            "title": "France Bleu Pays Basque (Bayonne)",
            "player": "pays-basque",
            "live": "grid/pays-basque",
        },
        "fbpaysdauvergne": {
            "title": "France Bleu Pays d'Auvergne (Clermont-Ferrand)",
            "player": "pays-d-auvergne",
            "live": "grid/pays-d-auvergne",
        },
        "fbpaysdesavoie": {
            "title": "France Bleu Pays de Savoie (Chambery)",
            "player": "pays-de-savoie",
            "live": "grid/pays-de-savoie",
        },
        "fbperigord": {"title": "France Bleu Périgord (Périgueux)", "player": "perigord", "live": "grid/perigord"},
        "fbpicardie": {"title": "France Bleu Picardie (Amiens)", "player": "picardie", "live": "grid/picardie"},
        "fbpoitou": {"title": "France Bleu Poitou (Poitiers)", "player": "poitou", "live": "grid/poitou"},
        "fbprovence": {
            "title": "France Bleu Provence (Aix-en-Provence)",
            "player": "provence",
            "live": "grid/provence",
        },
        "fbrcfm": {"title": "France Bleu RCFM", "player": "rcfm", "live": "grid/rcfm"},
        "fbsaintetienneloire": {
            "title": "France Bleu Saint-Etienne Loire",
            "player": "saint-etienne-loire",
            "live": "grid/saint-etienne-loire",
        },
        "fbroussillon": {"title": "France Bleu Roussillon", "player": "roussillon", "live": "grid/roussillon"},
        "fbsudlorraine": {
            "title": "France Bleu Sud Lorraine (Nancy)",
            "player": "sud-lorraine",
            "live": "grid/sud-lorraine",
        },
        "fbtoulouse": {"title": "France Bleu Toulouse", "player": "toulouse", "live": "grid/toulouse"},
        "fbtouraine": {"title": "France Bleu Touraine (Tours)", "player": "touraine", "live": "grid/touraine"},
        "fbvaucluse": {"title": "France Bleu Vaucluse (Avignon)", "player": "vaucluse", "live": "grid/vaucluse"},
    }

    def iter_resources(self, objs, split_path):
        if len(split_path) == 0:
            for _id, item in sorted(self._RADIOS.items()):
                if not _id.startswith("fb"):
                    yield Collection([_id], item["title"])
            yield Collection(["francebleu"], "France Bleu")

        elif split_path[0] == "francebleu":
            if len(split_path) == 1:
                for _id, item in sorted(self._RADIOS.items()):
                    if _id.startswith("fb"):
                        yield Collection([_id], item["title"])

            elif len(split_path) > 1 and split_path[1] in self._RADIOS:
                if len(split_path) == 2:
                    yield Collection([split_path[0], "direct"], "Direct")
                if "selection" in self._RADIOS[split_path[1]]:
                    yield Collection([split_path[0], "selection"], "Selection")

                elif len(split_path) == 3 and split_path[2] == "selection":
                    selection_url = self._RADIOS[split_path[1]]["selection"]
                    for item in self.browser.get_selection("francebleu", selection_url, split_path[1]):
                        yield item

                elif len(split_path) == 3 and split_path[2] == "direct":
                    yield self.get_radio(split_path[1])

            else:
                raise CollectionNotFound(split_path)

        elif len(split_path) == 1:
            yield Collection([split_path[0], "direct"], "Direct")
            if "selection" in self._RADIOS[split_path[0]]:
                yield Collection([split_path[0], "selection"], "Selection")
            if "podcast" in self._RADIOS[split_path[0]]:
                yield Collection([split_path[0], "podcasts"], "Podcast")

        elif len(split_path) == 2 and split_path[1] == "selection":
            for _id, item in sorted(self._RADIOS.items()):
                if _id == split_path[0]:
                    if "selection" in self._RADIOS[_id]:
                        selection_url = self._RADIOS[_id]["selection"]
                        for item in self.browser.get_selection(_id, selection_url, _id):
                            yield item
                        break

        elif len(split_path) == 2 and split_path[1] == "podcasts":
            for item in self.browser.get_podcast_emissions(
                split_path[0], self._RADIOS[split_path[0]]["podcast"], split_path
            ):
                yield item

        elif len(split_path) == 2 and split_path[1] == "direct":
            yield self.get_radio(split_path[0])

        elif len(split_path) == 3:
            podcasts_url = split_path[-1]
            if split_path[0] == "franceculture":
                podcasts_url = self.browser.get_france_culture_podcasts_url(split_path[-1])
            elif split_path[0] == "francetvinfo":
                podcasts_url = self.browser.get_francetvinfo_podcasts_url(split_path[-1])
            if podcasts_url:
                for item in self.browser.get_podcasts(podcasts_url):
                    yield item

        else:
            raise CollectionNotFound(split_path)

    def get_radio(self, radio):

        def create_stream(url, hd=True):
            stream = BaseAudioStream(0)
            if hd:
                stream.bitrate = 128
            else:
                stream.bitrate = 32
                url = url.replace("midfi", "lofi")

            stream.format = "mp3"
            stream.title = "%s kbits/s" % (stream.bitrate)
            stream.url = url
            return stream

        if not isinstance(radio, Radio):
            radio = Radio(radio)

        if radio.id not in self._RADIOS:
            return None

        title = self._RADIOS[radio.id]["title"]
        player_url = self._RADIOS[radio.id]["player"]
        radio.title = title
        radio.description = title
        radio_name = radio.id if not radio.id.startswith("fb") else "francebleu"
        url = self.browser.get_radio_url(radio_name, player_url)

        self.fillobj(radio, ("current",))
        radio.streams = [create_stream(url), create_stream(url, False)]
        return radio

    def fill_radio(self, radio, fields):
        if "current" in fields:
            title = self._RADIOS[radio.id]["title"]
            live_url = self._RADIOS[radio.id]["live"]
            radio_name = radio.id if not radio.id.startswith("fb") else "francebleu"
            artist, title = self.browser.get_current(radio_name, live_url)
            if not radio.current or radio.current is NotLoaded:
                radio.current = StreamInfo(0)
            radio.current.what = title
            radio.current.who = artist
        return radio

    def fill_audio(self, audio, fields):
        if "thumbnail" in fields and audio.thumbnail:
            audio.thumbnail.data = self.browser.open(audio.thumbnail.url)
        return audio

    def get_radio_id(self, audio_id):
        m = re.match(r"^\w+\.(\w+)\..*", audio_id)
        if m:
            return m.group(1)
        return ""

    def search_audio(self, pattern, sortby=CapAudio.SEARCH_RELEVANCE):
        for radio in self._RADIOS:
            if "selection" in self._RADIOS[radio]:
                selection_url = self._RADIOS[radio]["selection"]
                radio_url = radio if not radio.startswith("fb") else "francebleu"
                for item in self.browser.get_selection(radio_url, selection_url, radio):
                    if pattern.upper() in item.title.upper():
                        yield item

            if "podcast" in self._RADIOS[radio]:
                podcast_url = self._RADIOS[radio]["podcast"]
                radio_url = radio if not radio.startswith("fb") else "francebleu"
                for item in self.browser.get_podcast_emissions(radio_url, podcast_url, [radio]):
                    if pattern.upper() in item.title.upper():
                        podcasts_url = item.id
                        if radio == "franceculture":
                            podcasts_url = self.browser.get_france_culture_podcasts_url(item.id)
                        elif radio == "francetvinfo":
                            podcasts_url = self.browser.get_francetvinfo_podcasts_url(item.id)

                        for pod in self.browser.get_podcasts(podcasts_url):
                            yield pod

    def get_audio(self, _id):
        radio = self.get_radio_id(_id)
        if radio in self._RADIOS:
            if "selection" in self._RADIOS[radio]:
                selection_url = self._RADIOS[radio]["selection"]
                radio_url = radio if not radio.startswith("fb") else "francebleu"
                return self.browser.get_audio(_id, radio_url, selection_url, radio)
        elif radio == "podcast":
            m = re.match(r"audio\.podcast\.(\d*)-.*", _id)
            if m:
                for item in self.browser.get_podcasts(m.group(1)):
                    if _id == item.id:
                        return item

    def iter_radios_search(self, pattern):
        for key, radio in self._RADIOS.items():
            if pattern.lower() in radio["title"].lower() or pattern.lower() in key.lower():
                yield self.get_radio(key)

    OBJECTS = {Radio: fill_radio, BaseAudio: fill_audio}
