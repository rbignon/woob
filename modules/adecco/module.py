# Copyright(C) 2013      Bezleputh
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

from collections import OrderedDict

from woob.capabilities.job import BaseJobAdvert, CapJob
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value

from .browser import AdeccoBrowser


__all__ = ["AdeccoModule"]


class AdeccoModule(Module, CapJob):
    NAME = "adecco"
    DESCRIPTION = "adecco website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"

    BROWSER = AdeccoBrowser

    publicationDate_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "000000": "-- Indifferent --",
                    "2": "Moins de 48 heures",
                    "7": "Moins de 1 semaine",
                    "14": "Moins de 2 semaines",
                }.items()
            )
        ]
    )

    type_contract_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "-- Indifferent --",
                    "ADCFREMP005": "CDD",
                    "ADCFREMP004": "CDI",
                    "ADCFREMP003": "Intérim",
                    "ADCFREMP009": "Autres",
                    "ADCFREMP010": "Libéral",
                }.items()
            )
        ]
    )

    places_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "-- Indifferent --",
                    "AIN": "Ain",
                    "AISNE": "Aisne",
                    "ALLIER": "Allier",
                    "ALPES-DE-HAUTE-PROVENCE": "Alpes-De-Haute-Provence",
                    "ALPES-MARITIMES": "Alpes-Maritimes",
                    "ARDECHE": "Ardeche",
                    "ARDENNES": "Ardennes",
                    "ARIEGE": "Ariege",
                    "AUBE": "Aube",
                    "AUDE": "Aude",
                    "AVEYRON": "Aveyron",
                    "BAS-RHIN": "Bas-Rhin",
                    "BOUCHES-DU-RHONE": "Bouches-Du-Rhone",
                    "CALVADOS": "Calvados",
                    "CANTAL": "Cantal",
                    "CHARENTE": "Charente",
                    "CHARENTE-MARITIME": "Charente-Maritime",
                    "CHER": "Cher",
                    "CORREZE": "Correze",
                    "CORSE-DU-SUD": "Corse du Sud",
                    "COTE-D%27OR": "Cote D'Or",
                    "COTES-D%27ARMOR": "Cotes D'Armor",
                    "CREUSE": "Creuse",
                    "DEUX-SEVRES": "Deux-Sevres",
                    "DORDOGNE": "Dordogne",
                    "DOUBS": "Doubs",
                    "DROME": "Drome",
                    "ESSONNE": "Essonne",
                    "EURE": "Eure",
                    "EURE-ET-LOIR": "Eure-Et-Loir",
                    "FINISTERE": "Finistere",
                    "GARD": "Gard",
                    "GERS": "Gers",
                    "GIRONDE": "Gironde",
                    "GUADELOUPE": "Guadeloupe",
                    "GUYANE": "Guyane",
                    "HAUT-RHIN": "Haut-Rhin",
                    "HAUTE-CORSE": "Haute-Corse",
                    "HAUTE-GARONNE": "Haute-Garonne",
                    "HAUTE-LOIRE": "Haute-Loire",
                    "HAUTE-MARNE": "Haute-Marne",
                    "HAUTE-SAONE": "Haute-Saone",
                    "HAUTE-SAVOIE": "Haute-Savoie",
                    "HAUTE-VIENNE": "Haute-Vienne",
                    "HAUTES-ALPES": "Hautes-Alpes",
                    "HAUTES-PYRENEES": "Hautes-Pyrenees",
                    "HAUTS-DE-SEINE": "Hauts-De-Seine",
                    "HERAULT": "Herault",
                    "ILLE-ET-VILAINE": "Ille-Et-Vilaine",
                    "INDRE": "Indre",
                    "INDRE-ET-LOIRE": "Indre-Et-Loire",
                    "ISERE": "Isere",
                    "JURA": "Jura",
                    "LA+REUNION": "La Reunion",
                    "LANDES": "Landes",
                    "LOIR-ET-CHER": "Loir-Et-Cher",
                    "LOIRE": "Loire",
                    "LOIRE-ATLANTIQUE": "Loire-Atlantique",
                    "LOIRET": "Loiret",
                    "LOT": "Lot",
                    "LOT-ET-GARONNE": "Lot-Et-Garonne",
                    "LOZERE": "Lozere",
                    "MAINE-ET-LOIRE": "Maine-Et-Loire",
                    "MANCHE": "Manche",
                    "MARNE": "Marne",
                    "MARTINIQUE": "Martinique",
                    "MAYENNE": "Mayenne",
                    "MAYOTTE": "Mayotte",
                    "MEURTHE-ET-MOSELLE": "Meurthe et Moselle",
                    "MEUSE": "Meuse",
                    "MONACO": "Monaco",
                    "MORBIHAN": "Morbihan",
                    "MOSELLE": "Moselle",
                    "NIEVRE": "Nievre",
                    "NORD": "Nord",
                    "OISE": "Oise",
                    "ORNE": "Orne",
                    "PARIS": "Paris",
                    "PAS-DE-CALAIS": "Pas-de-Calais",
                    "PUY-DE-DOME": "Puy-de-Dome",
                    "PYRENEES-ATLANTIQUES": "Pyrenees-Atlantiques",
                    "PYRENEES-ORIENTALES": "Pyrenees-Orientales",
                    "RHONE": "Rhone",
                    "SAONE-ET-LOIRE": "Saone-et-Loire",
                    "SARTHE": "Sarthe",
                    "SAVOIE": "Savoie",
                    "SEINE-ET-MARNE": "Seine-et-Marne",
                    "SEINE-MARITIME": "Seine-Maritime",
                    "SEINE-SAINT-DENIS": "Seine-Saint-Denis",
                    "SOMME": "Somme",
                    "ST+PIERRE+ET+MIQUELON": "St Pierre et Miquelon",
                    "SUISSE": "Suisse",
                    "TARN": "Tarn",
                    "TARN-ET-GARONNE": "Tarn-et-Garonne",
                    "TERRITOIRE+DE+BELFORT": "Territoire de Belfort",
                    "VAL-D%27OISE": "Val-D'Oise",
                    "VAL-DE-MARNE": "Val-De-Marne",
                    "VAR": "Var",
                    "VAUCLUSE": "Vaucluse",
                    "VENDEE": "Vendee",
                    "VIENNE": "Vienne",
                    "VOSGES": "Vosges",
                    "YONNE": "Yonne",
                    "YVELINES": "Yvelines",
                }.items()
            )
        ]
    )

    activityDomain_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "Z": "-- Indifferent --",
                    "A": "Accueil - Secrétariat - Fonctions Administratives",
                    "B": "Achats - Juridique - Qualité - RH - Direction",
                    "C": "Agriculture - Viticulture - Pêche - Espaces Verts",
                    "D": "Automobile",
                    "E": "Banque - Finance - Gestion Comptabilité - Assurance",
                    "F": "Bâtiment - Travaux Publics - Architecture - Immobilier",
                    "G": "Bureaux d'Etudes - Méthodes",
                    "H": "Commerce - Vente - Grande Distribution",
                    "I": "Environnement - Nettoyage - Sécurité",
                    "J": "Hôtellerie - Restauration - Métiers de Bouche",
                    "K": "Industrie",
                    "L": "Informatique - Technologie de l'Information",
                    "M": "Logistique - Manutention - Transport",
                    "N": "Marketing - Communication - Imprimerie - Edition",
                    "O": "Médical - Paramédical - Esthétique",
                    "P": "Pharmacie (Industrie, Officine) - Recherche clinique",
                    "Q": "Télémarketing - Téléservices",
                    "R": "Tourisme - Loisirs - Spectacle - Audiovisuel",
                }.items()
            )
        ]
    )

    CONFIG = BackendConfig(
        Value("job", label="Job name", masked=False, default=""),
        Value("town", label="Town name", masked=False, default=""),
        Value("place", label="County", choices=places_choices),
        Value("publication_date", label="Publication Date", choices=publicationDate_choices),
        Value("contract", labe="Contract type", choices=type_contract_choices),
        Value("activity_domain", label="Activity Domain", choices=activityDomain_choices, default=""),
    )

    def search_job(self, pattern=None):
        yield from self.browser.search_job(pattern)

    def advanced_search_job(self):
        activity_domain = self.config["activity_domain"].get() if self.config["activity_domain"].get() != "Z" else None

        yield from self.browser.advanced_search_job(
            publication_date=int(self.config["publication_date"].get()),
            contract_type=self.config["contract"].get(),
            conty=self.config["place"].get(),
            activity_domain=activity_domain,
            job=self.config["job"].get(),
            town=self.config["town"].get(),
        )

    def get_job_advert(self, _id, advert=None):
        return self.browser.get_job_advert(_id, advert)

    def fill_obj(self, advert, fields):
        return self.get_job_advert(advert.id, advert)

    OBJECTS = {BaseJobAdvert: fill_obj}
