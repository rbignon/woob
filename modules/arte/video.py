# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz
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


def enum(**enums):
    _values = list(enums.values())
    _keys = list(enums.keys())
    _items = list(enums.items())
    _types = list((type(value) for value in enums.values()))
    _index = {
        (value if not isinstance(value, dict) else next(iter(value.values()))): i
        for i, value in enumerate(enums.values())
    }

    enums["keys"] = _keys
    enums["values"] = _values
    enums["items"] = _items
    enums["index"] = _index
    enums["types"] = _types
    return type("Enum", (), enums)


FORMATS = enum(HTTP_MP4="HBBTV", HLS="M3U8", RTMP="RTMP", HLS_MOBILE="MOBILE")

LANG = enum(
    FRENCH={"label": "French", "webservice": "F", "site": "fr", "version": "1", "title": "titleFR"},
    GERMAN={"label": "German", "webservice": "D", "site": "de", "version": "1", "title": "titleDE"},
)

CONCERT = enum(
    CLASSIQUE={"id": "CLA", "label": "Classique"},
    ACTUELLE={"id": "MUA", "label": "Musiques actuelles"},
    OPERA={"id": "OPE", "label": "Opera"},
    JAZZ={"id": "JAZ", "label": "Jazz"},
    MONDE={"id": "MUD", "label": "Musiques du monde"},
    SCENE={"id": "ADS", "label": "Arts de la scène"},
    COLLECTION={"id": "collections_ARS", "label": "Collections"},
    PLAYLIST={"id": "playlists_ARS", "label": "Playlists"},
)

CINEMA = enum(
    FILM={"id": "FLM", "label": "Films"},
    CLASSIQUES={"id": "MCL", "label": "Les grands du 7e art"},
    COURT_METRAGES={"id": "CMG", "label": "Courts métrages"},
    FILM_MUETS={"id": "CMU", "label": "Films muets"},
    ACTU={"id": "ACC", "label": "Actualité du cinéma"},
    COLLECTION={"id": "collections_CIN", "label": "Collections"},
    MAGAZINE={"id": "magazines_CIN", "label": "Émissions"},
)

SERIE = enum(
    SERIES={"id": "SES", "label": "Séries"},
    FICTIONS={"id": "FIC", "label": "Fictions"},
    HUMOUR={"id": "CHU", "label": "Courts humoristiques"},
    COLLECTION={"id": "collections_SER", "label": "Collections"},
)

POP = enum(
    POP={"id": "POP", "label": "Culture pop"},
    ART={"id": "ART", "label": "Arts"},
    IDE={"id": "IDE", "label": "Idées"},
    COLLECTION={"id": "collections_CPO", "label": "Collections"},
    MAGAZINE={"id": "magazines_CPO", "label": "Émissions"},
)

SCIENCE = enum(
    POP={"id": "SAN", "label": "Médecine et santé"},
    EEN={"id": "ENN", "label": "Environnement et nature"},
    TEC={"id": "TEC", "label": "Technologies et innovations"},
    ENB={"id": "ENB", "label": "En bref"},
    COLLECTION={"id": "collections_SCI", "label": "Collections"},
    MAGAZINE={"id": "magazines_SCI", "label": "Émissions"},
)

VOYAGE = enum(
    NEA={"id": "NEA", "label": "Nature et animaux"},
    EVA={"id": "EVA", "label": "Evasion"},
    ATA={"id": "ATA", "label": "A table !"},
    VIA={"id": "VIA", "label": "Vies d'ailleurs"},
    COLLECTION={"id": "collections_DEC", "label": "Collections"},
    MAGAZINE={"id": "magazines_DEC", "label": "Émissions"},
)

HISTOIRE = enum(
    XXE={"id": "XXE", "label": "XXe siècle"},
    CIV={"id": "CIV", "label": "Civilisations"},
    LGP={"id": "LGP", "label": "Les grands personnages"},
    COLLECTION={"id": "collections_DEC", "label": "Collections"},
)

SITE = enum(
    PROGRAM={"id": "program", "label": "Arte Programs"},
    CREATIVE={"id": "creative", "label": "Arte Creative"},
    GUIDE={"id": "guide", "label": "Arte Guide TV"},
    CONCERT={"id": "concert", "label": "Arte Concert videos", "enum": CONCERT},
    CINEMA={"id": "cinema", "label": "Arte Cinema", "enum": CINEMA},
    SERIE={"id": "series-et-fictions", "label": "Arte CreativeSéries et fictions", "enum": SERIE},
    POP={"id": "culture-et-pop", "label": "Culture et pop", "enum": POP},
    SCIENCE={"id": "sciences", "label": "Sciences", "enum": SCIENCE},
    VOYAGE={"id": "voyages-et-decouvertes", "label": "Voyages et découvertes", "enum": VOYAGE},
    HISTOIRE={"id": "histoire", "label": "Histoire", "enum": HISTOIRE},
)

QUALITY = enum(
    HD={"label": "SQ", "order": 3},
    MD={"label": "EQ", "order": 2},
    SD={"label": "MQ", "order": 1},
    LD={"label": "LQ", "order": 0},
    XD={"label": "XQ", "order": 4},
)

VERSION_VIDEO = enum(
    VOSTA={"label": "Original version subtitled (German)", LANG.GERMAN.get("label"): "3"},
    VOSTF={"label": "Original version subtitled (French)", LANG.FRENCH.get("label"): "3"},
    VASTA={"label": "Translated version (German)", LANG.GERMAN.get("label"): "1", LANG.FRENCH.get("label"): "2"},
    VFSTF={"label": "Translated version (French)", LANG.FRENCH.get("label"): "1", LANG.GERMAN.get("label"): "2"},
    VASTMA={"label": "Deaf version (German)", LANG.GERMAN.get("label"): "8"},
    VFSTMF={"label": "Deaf version (French)", LANG.FRENCH.get("label"): "8"},
)


def get_site_enum_by_id(id):
    for s in SITE.values:
        if s.get("id") == id:
            return s
    return
