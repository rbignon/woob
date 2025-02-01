# -*- coding: utf-8 -*-

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
from woob.tools.value import Value, ValueInt

from .browser import PoleEmploiBrowser


__all__ = ["PoleEmploiModule"]


class PoleEmploiModule(Module, CapJob):
    NAME = "poleemploi"
    DESCRIPTION = "Pole Emploi website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    VERSION = "3.7"

    BROWSER = PoleEmploiBrowser

    places_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "100|PAYS|01": "France entière",
                    "100|REGION|84": "Auvergne-Rhône-Alpes",
                    "101|DEPARTEMENT|01": "-- Ain (01)",
                    "102|DEPARTEMENT|03": "-- Allier (03)",
                    "103|DEPARTEMENT|07": "-- Ardèche (07)",
                    "104|DEPARTEMENT|15": "-- Cantal (15)",
                    "105|DEPARTEMENT|26": "-- Drôme (26)",
                    "106|DEPARTEMENT|38": "-- Isère (38)",
                    "107|DEPARTEMENT|42": "-- Loire (42)",
                    "108|DEPARTEMENT|43": "-- Haute-Loire (43)",
                    "109|DEPARTEMENT|63": "-- Puy-de-Dôme (63)",
                    "110|DEPARTEMENT|69": "-- Rhône (69)",
                    "111|DEPARTEMENT|73": "-- Savoie (73)",
                    "112|DEPARTEMENT|74": "-- Haute-Savoie (74) ",
                    "113|REGION|27": "Bourgogne-Franche-Comté",
                    "114|DEPARTEMENT|21": "-- Côte-d'Or (21)",
                    "115|DEPARTEMENT|25": "-- Doubs (25)",
                    "116|DEPARTEMENT|39": "-- Jura (39)",
                    "117|DEPARTEMENT|58": "-- Nièvre (58)",
                    "118|DEPARTEMENT|70": "-- Haute-Saône (70)",
                    "119|DEPARTEMENT|71": "-- Saône-et-Loire (71)",
                    "120|DEPARTEMENT|89": "-- Yonne (89)",
                    "121|DEPARTEMENT|90": "-- Territoire de Belfort (90) ",
                    "122|REGION|53": "Bretagne",
                    "123|DEPARTEMENT|22": "-- Côtes-d'Armor (22)",
                    "124|DEPARTEMENT|29": "-- Finistère (29)",
                    "125|DEPARTEMENT|35": "-- Ille-et-Vilaine (35)",
                    "126|DEPARTEMENT|56": "-- Morbihan (56) ",
                    "127|REGION|24": "Centre-Val de Loire",
                    "128|DEPARTEMENT|": "-- Cher (18)",
                    "129|DEPARTEMENT|": "-- Eure-et-Loir (28)",
                    "130|DEPARTEMENT|": "-- Indre (36)",
                    "131|DEPARTEMENT|": "-- Indre-et-Loire (37)",
                    "132|DEPARTEMENT|": "-- Loir-et-Cher (41)",
                    "133|DEPARTEMENT|": "-- Loiret (45) ",
                    "134|REGION|94": "Corse",
                    "135|DEPARTEMENT|2A": "-- Corse-du-Sud (2A)",
                    "136|DEPARTEMENT|2B": "-- Haute-Corse (2B)",
                    "137|REGION|44": "Grand Est",
                    "138|DEPARTEMENT|08": "-- Ardennes (08)",
                    "139|DEPARTEMENT|10": "-- Aube (10)",
                    "140|DEPARTEMENT|51": "-- Marne (51)",
                    "141|DEPARTEMENT|52": "-- Haute-Marne (52)",
                    "142|DEPARTEMENT|54": "-- Meurthe-et-Moselle (54)",
                    "143|DEPARTEMENT|55": "-- Meuse (55)",
                    "144|DEPARTEMENT|57": "-- Moselle (57)",
                    "145|DEPARTEMENT|67": "-- Bas-Rhin (67)",
                    "146|DEPARTEMENT|68": "-- Haut-Rhin (68)",
                    "147|DEPARTEMENT|88": "-- Vosges (88) ",
                    "148|REGION|32": "Hauts-de-France",
                    "149|DEPARTEMENT|02": "-- Aisne (02)",
                    "150|DEPARTEMENT|59": "-- Nord (59)",
                    "151|DEPARTEMENT|60": "-- Oise (60)",
                    "152|DEPARTEMENT|62": "-- Pas-de-Calais (62)",
                    "153|DEPARTEMENT|80": "-- Somme (80) ",
                    "154|REGION|11": "Île-de-France",
                    "155|DEPARTEMENT|75": "-- Paris (75)",
                    "156|DEPARTEMENT|77": "-- Seine-et-Marne (77)",
                    "157|DEPARTEMENT|78": "-- Yvelines (78)",
                    "158|DEPARTEMENT|91": "-- Essonne (91)",
                    "159|DEPARTEMENT|92": "-- Hauts-de-Seine (92)",
                    "160|DEPARTEMENT|93": "-- Seine-Saint-Denis (93)",
                    "161|DEPARTEMENT|94": "-- Val-de-Marne (94)",
                    "162|DEPARTEMENT|95": "-- Val-d'Oise (95) ",
                    "163|REGION|28": "Normandie",
                    "164|DEPARTEMENT|14": "-- Calvados (14)",
                    "165|DEPARTEMENT|27": "-- Eure (27)",
                    "166|DEPARTEMENT|50": "-- Manche (50)",
                    "167|DEPARTEMENT|61": "-- Orne (61)",
                    "168|DEPARTEMENT|76": "-- Seine-Maritime (76)",
                    "169|REGION|75": "Nouvelle-Aquitaine",
                    "170|DEPARTEMENT|16": "-- Charente (16)",
                    "171|DEPARTEMENT|17": "-- Charente-Maritime (17)",
                    "172|DEPARTEMENT|19": "-- Corrèze (19)",
                    "173|DEPARTEMENT|23": "-- Creuse (23)",
                    "174|DEPARTEMENT|24": "-- Dordogne (24)",
                    "175|DEPARTEMENT|33": "-- Gironde (33)",
                    "176|DEPARTEMENT|40": "-- Landes (40)",
                    "177|DEPARTEMENT|47": "-- Lot-et-Garonne (47)",
                    "178|DEPARTEMENT|64": "-- Pyrénées-Atlantiques (64)",
                    "179|DEPARTEMENT|79": "-- Deux-Sèvres (79)",
                    "180|DEPARTEMENT|86": "-- Vienne (86)",
                    "181|DEPARTEMENT|87": "-- Haute-Vienne (87) ",
                    "182|REGION|76": "Occitanie",
                    "183|DEPARTEMENT|09": "-- Ariège (09)",
                    "184|DEPARTEMENT|11": "-- Aude (11)",
                    "185|DEPARTEMENT|12": "-- Aveyron (12)",
                    "186|DEPARTEMENT|30": "-- Gard (30)",
                    "187|DEPARTEMENT|31": "-- Haute-Garonne (31)",
                    "188|DEPARTEMENT|32": "-- Gers (32)",
                    "189|DEPARTEMENT|34": "-- Hérault (34)",
                    "190|DEPARTEMENT|46": "-- Lot (46)",
                    "191|DEPARTEMENT|48": "-- Lozère (48)",
                    "192|DEPARTEMENT|65": "-- Hautes-Pyrénées (65)",
                    "193|DEPARTEMENT|66": "-- Pyrénées-Orientales (66)",
                    "194|DEPARTEMENT|81": "-- Tarn (81)",
                    "195|DEPARTEMENT|82": "-- Tarn-et-Garonne (82) ",
                    "196|REGION|52": "Pays de la Loire",
                    "197|DEPARTEMENT|44": "-- Loire-Atlantique (44)",
                    "198|DEPARTEMENT|49": "-- Maine-et-Loire (49)",
                    "199|DEPARTEMENT|53": "-- Mayenne (53)",
                    "200|DEPARTEMENT|72": "-- Sarthe (72)",
                    "201|DEPARTEMENT|85": "-- Vendée (85) ",
                    "202|REGION|93": "Provence-Alpes-Côte d'Azur",
                    "203|DEPARTEMENT|04": "-- Alpes-de-Haute-Provence (04)",
                    "204|DEPARTEMENT|05": "-- Hautes-Alpes (05)",
                    "205|DEPARTEMENT|06": "-- Alpes-Maritimes (06)",
                    "206|DEPARTEMENT|13": "-- Bouches-du-Rhône (13)",
                    "207|DEPARTEMENT|83": "-- Var (83)",
                    "208|DEPARTEMENT|84": "-- Vaucluse (84)",
                    "209|REGION|01": "Guadeloupe",
                    "210|REGION|02": "Martinique",
                    "211|REGION|03": "Guyane",
                    "212|REGION|04": "La Réunion",
                    "213|REGION|05": "Mayotte",
                    "214|DEPARTEMENT|975": "Saint-Pierre-et-Miquelon",
                    "215|DEPARTEMENT|977": "Saint-Barthélemy",
                    "216|DEPARTEMENT|978": "Saint-Martin",
                    "217|DEPARTEMENT|986": "Wallis-et-Futuna",
                    "218|DEPARTEMENT|987": "Polynésie française",
                    "219|DEPARTEMENT|988": "Nouvelle-Calédonie",
                    "220|DEPARTEMENT|989": "Clipperton",
                }.items()
            )
        ]
    )

    type_contrat_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "Tous types de contrats",
                    "CDI": "CDI tout public",
                    "CDI&natureOffre=E2": "CDI alternance",
                    "CDI&natureOffre=FS": "CDI insertion",
                    "CDD": "CDD tout public",
                    "CDD&natureOffre=E2": "CDD alternance",
                    "CDD&natureOffre=FS": "CDD insertion",
                    "CDS": "CDD Senior",
                    "MID": "Mission d'intérim",
                    "SAI": "Contrat de travail saisonnier",
                    "INT": "Contrat de travail intermittent",
                    "FRA": "Franchise",
                    "LIB": "Profession libérale",
                    "REP": "Reprise d'entreprise",
                    "CCE": "Profession commerciale",
                }.items()
            )
        ]
    )

    qualification_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "Toute Qualification",
                    "1": "Manoeuvre",
                    "2": "Ouvrier spécialisé",
                    "3": "Ouvrier qualifié (P1,P2)",
                    "4": "Ouvrier qualifié (P3,P4,OHQ)",
                    "5": "Employé non qualifié",
                    "6": "Employé qualifié",
                    "7": "Technicien",
                    "8": "Agent de maîtrise",
                    "9": "Cadre",
                }.items()
            )
        ]
    )

    limit_date_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "Aucune limite",
                    "1": "Hier",
                    "3": "3 jours",
                    "7": "1 semaine",
                    "14": "2 semaines",
                    "31": "1 mois",
                    "93": "3 mois",
                }.items()
            )
        ]
    )

    domain_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "Tout secteur d'activité",
                    "M": "Achats / Comptabilité / Gestion",
                    "B": "Arts / Artisanat d'art",
                    "C": "Banque / Assurance",
                    "F": "Bâtiment / Travaux Publics",
                    "D": "Commerce / Vente",
                    "E": "Communication / Multimédia",
                    "M14": "Conseil / Etudes",
                    "M13": "Direction d'entreprise",
                    "A": "Espaces verts et naturels / Agriculture / Pêche / Soins aux animaux",
                    "G": "Hôtellerie - Restauration / Tourisme / Animation",
                    "C15": "Immobilier",
                    "H": "Industrie",
                    "M18": "Informatique / Télécommunication",
                    "I": "Installation / Maintenance",
                    "M17": "Marketing / Stratégie commerciale",
                    "M15": "Ressources Humaines",
                    "J": "Santé",
                    "M16": "Secrétariat / Assistanat",
                    "K": "Services à la personne / à la collectivité",
                    "L": "Spectacle",
                    "L14": "Sport",
                    "N": "Transport / Logistique",
                }.items()
            )
        ]
    )

    CONFIG = BackendConfig(
        Value("metier", label="Job name", masked=False, default=""),
        Value("place", label="Place", choices=places_choices, default="100|FRANCE|01"),
        Value("contrat", label="Contract", choices=type_contrat_choices, default=""),
        ValueInt("salary", label="Salary/Year", default=0),
        Value("qualification", label="Qualification", choices=qualification_choices, default=""),
        Value("limit_date", label="Date limite", choices=limit_date_choices, default=""),
        Value("domain", label="Domain", choices=domain_choices, default=""),
    )

    def search_job(self, pattern=None):
        return self.browser.search_job(pattern=pattern)

    def advanced_search_job(self):
        return self.browser.advanced_search_job(
            metier=self.config["metier"].get(),
            place=self.config["place"].get(),
            contrat=self.config["contrat"].get(),
            salary=self.config["salary"].get(),
            qualification=self.config["qualification"].get(),
            limit_date=self.config["limit_date"].get(),
            domain=self.config["domain"].get(),
        )

    def get_job_advert(self, _id, advert=None):
        return self.browser.get_job_advert(_id, advert)

    def fill_obj(self, advert, fields):
        return self.get_job_advert(advert.id, advert)

    OBJECTS = {BaseJobAdvert: fill_obj}
