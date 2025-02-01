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

from .browser import ApecBrowser
from .job import APEC_CONTRATS, APEC_EXPERIENCE


__all__ = ["ApecModule"]


class ApecModule(Module, CapJob):
    NAME = "apec"
    DESCRIPTION = "apec website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"

    BROWSER = ApecBrowser

    places_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "001|99700": "UE Hors France",
                    "002|99126": "..Grèce",
                    "003|99132": "..Royaume Uni",
                    "004|99134": "..Espagne",
                    "005|99136": "..Irlande",
                    "006|99139": "..Portugal",
                    "007|99254": "..Chypre",
                    "008|99127": "..Italie",
                    "009|99131": "..Belgique",
                    "010|99135": "..Pays Bas",
                    "011|99137": "..Luxembourg",
                    "012|99144": "..Malte",
                    "013|99145": "..Slovénie",
                    "014|99101": "..Danemark",
                    "015|99104": "..Suède",
                    "016|99105": "..Finlande",
                    "017|99106": "..Estonie",
                    "018|99107": "..Lettonie",
                    "019|99108": "..Lituanie",
                    "020|99109": "..Allemagne",
                    "021|99110": "..Autriche",
                    "022|99111": "..Bulgarie",
                    "023|99112": "..Hongrie",
                    "024|99114": "..Roumanie",
                    "025|99116": "..République Tchèque",
                    "026|99117": "..Slovaquie",
                    "027|99119": "..Croatie",
                    "028|99122": "..Pologne",
                    "029|799": "France",
                    "030|711": "..Ile-de-France",
                    "031|75": "....Paris",
                    "032|77": "....Seine-et-Marne",
                    "033|78": "....Yvelines",
                    "034|91": "....Essonne",
                    "035|92": "....Hauts-de-Seine",
                    "036|93": "....Seine-Saint-Denis",
                    "037|94": "....Val-de-Marne",
                    "038|95": "....Val-d'Oise",
                    "039|703": "..Basse-Normandie",
                    "040|14": "....Calvados",
                    "041|50": "....Manche",
                    "042|61": "....Orne",
                    "043|705": "..Bretagne",
                    "044|22": "....Côtes d'Armor",
                    "045|29": "....Finistère",
                    "046|35": "....Ille-et-Vilaine",
                    "047|56": "....Morbihan",
                    "048|706": "..Centre",
                    "049|18": "....Cher",
                    "050|28": "....Eure-et-Loir",
                    "051|36": "....Indre",
                    "052|37": "....Indre-et-Loire",
                    "053|41": "....Loir-et-Cher",
                    "054|45": "....Loiret",
                    "055|710": "..Haute-Normandie",
                    "056|27": "....Eure",
                    "057|76": "....Seine-Maritime",
                    "058|717": "..Pays de La Loire",
                    "059|44": "....Loire-Atlantique",
                    "060|49": "....Maine-et-Loire",
                    "061|53": "....Mayenne",
                    "062|72": "....Sarthe",
                    "063|85": "....Vendée",
                    "064|700": "..Alsace",
                    "065|67": "....Bas-Rhin",
                    "066|68": "....Haut-Rhin",
                    "067|704": "..Bourgogne",
                    "068|21": "....Côte d'Or",
                    "069|58": "....Nièvre",
                    "070|71": "....Saône-et-Loire",
                    "071|89": "....Yonne",
                    "072|707": "..Champagne",
                    "073|8": "....Ardennes",
                    "074|10": "....Aube",
                    "075|51": "....Marne",
                    "076|52": "....Haute-Marne",
                    "077|709": "..Franche-Comté",
                    "078|25": "....Doubs",
                    "079|39": "....Jura",
                    "080|70": "....Haute-Saône",
                    "081|90": "....Territoire de Belfort",
                    "082|714": "..Lorraine",
                    "083|54": "....Meurthe-et-Moselle",
                    "084|55": "....Meuse",
                    "085|57": "....Moselle",
                    "086|88": "....Vosges",
                    "087|716": "..Nord-Pas-de-Calais",
                    "088|59": "....Nord",
                    "089|62": "....Pas-de-Calais",
                    "090|718": "..Picardie",
                    "091|2": "....Aisne",
                    "092|60": "....Oise",
                    "093|80": "....Somme",
                    "094|20": "..Corse",
                    "095|750": "....Corse du Sud",
                    "096|751": "....Haute-Corse",
                    "097|702": "..Auvergne",
                    "098|3": "....Allier",
                    "099|15": "....Cantal",
                    "100|43": "....Haute-Loire",
                    "101|63": "....Puy-de-Dôme",
                    "102|720": "..PACA",
                    "103|4": "....Alpes-de-Haute-Provence",
                    "104|5": "....Hautes-Alpes",
                    "105|6": "....Alpes-Maritimes",
                    "106|13": "....Bouches-du-Rhône",
                    "107|83": "....Var",
                    "108|84": "....Vaucluse",
                    "109|721": "..Rhône-Alpes",
                    "110|1": "....Ain",
                    "111|7": "....Ardèche",
                    "112|26": "....Drôme",
                    "113|38": "....Isère",
                    "114|42": "....Loire",
                    "115|69": "....Rhône",
                    "116|73": "....Savoie",
                    "117|74": "....Haute-Savoie",
                    "118|701": "..Aquitaine",
                    "119|24": "....Dordogne",
                    "120|33": "....Gironde",
                    "121|40": "....Landes",
                    "122|47": "....Lot-et-Garonne",
                    "123|64": "....Pyrénées-Atlantiques",
                    "124|712": "..Languedoc-Roussillon",
                    "125|11": "....Aude",
                    "126|30": "....Gard",
                    "127|34": "....Hérault",
                    "128|48": "....Lozère",
                    "129|66": "....Pyrénées-Orientales",
                    "130|713": "..Limousin",
                    "131|19": "....Corrèze",
                    "132|23": "....Creuse",
                    "133|87": "....Haute-Vienne",
                    "134|715": "..Midi-Pyrénées",
                    "135|9": "....Ariège",
                    "136|12": "....Aveyron",
                    "137|31": "....Haute-Garonne",
                    "138|32": "....Gers",
                    "139|46": "....Lot",
                    "140|65": "....Hautes-Pyrénées",
                    "141|81": "....Tarn",
                    "142|82": "....Tarn-et-Garonne",
                    "143|719": "..Poitou-Charentes",
                    "144|16": "....Charente",
                    "145|17": "....Charente-Maritime",
                    "146|79": "....Deux-Sèvres",
                    "147|86": "....Vienne",
                    "148|99712": "..France Outre-Mer",
                    "149|99519": "....Terres Australes et Antarctiques Françaises",
                    "150|97100": "....Guadeloupe",
                    "151|97200": "....Martinique",
                    "152|97300": "....Guyane",
                    "153|97400": "....La Réunion",
                    "154|97500": "....Saint-Pierre-et-Miquelon",
                    "155|97600": "....Mayotte",
                    "156|98300": "....Polynésie Française",
                    "157|98600": "....Wallis et Futuna",
                    "158|98800": "....Nouvelle Calédonie",
                    "159|97800": "....Saint-Martin",
                    "160|97700": "....Saint-Barthélémy",
                    "161|102099": "International",
                    "162|99715": "..Afrique",
                    "163|99716": "..Asie",
                    "164|99700": "..UE Hors France",
                    "165|99701": "..Europe Hors UE",
                    "166|99702": "..Amérique du Nord",
                    "167|99711": "..Océanie",
                    "168|99714": "..Amérique Latine",
                }.items()
            )
        ]
    )

    fonction_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "00|": "-- Indifférent --",
                    "01|101828": "Commercial, Marketing",
                    "02|101782": ".....Administration des ventes et SAV",
                    "03|101783": ".....Chargé d'affaires, technico-commercial",
                    "04|101784": ".....Commercial",
                    "05|101785": ".....Commerce international",
                    "06|101786": ".....Direction commerciale et marketing",
                    "07|101787": ".....Direction régionale et d'agence",
                    "08|101788": ".....Marketing",
                    "09|101789": ".....Ventes en magasin",
                    "10|101829": "Communication, Création",
                    "11|101790": ".....Communication",
                    "12|101791": ".....Création",
                    "13|101792": ".....Documentation, rédaction technique",
                    "14|101793": ".....Journalisme, édition",
                    "15|101830": "Direction d'entreprise",
                    "16|101794": ".....Adjoint, conseil de direction",
                    "17|101795": ".....Direction générale",
                    "18|101831": "Etudes, Recherche et Développement",
                    "19|101796": ".....Conception, recherche",
                    "20|101797": ".....Direction recherche et développement",
                    "21|101798": ".....Etudes socio-économiques",
                    "22|101799": ".....Projets scientifiques et techniques",
                    "23|101800": ".....Test, essai, validation, expertise",
                    "24|101832": "Gestion, Finance, Administration",
                    "25|101801": ".....Administration, gestion, organisation",
                    "26|101802": ".....Comptabilité",
                    "27|101803": ".....Contrôle de gestion, audit",
                    "28|101804": ".....Direction gestion, finance",
                    "29|101805": ".....Droit, fiscalité",
                    "30|101806": ".....Finance, trésorerie",
                    "31|101833": "Informatique",
                    "32|101807": ".....Direction informatique",
                    "33|101808": ".....Exploitation, maintenance informatique",
                    "34|101809": ".....Informatique de gestion",
                    "35|101810": ".....Informatique industrielle",
                    "36|101811": ".....Informatique web, sites et portails Internet",
                    "37|101812": ".....Maîtrise d'ouvrage et fonctionnel",
                    "38|101813": ".....Système, réseaux, données",
                    "39|101834": "Production Industrielle, Travaux, Chantiers",
                    "40|101814": ".....Cadres de chantier",
                    "41|101815": ".....Cadres de production industrielle",
                    "42|101816": ".....Direction d'unité industrielle",
                    "43|101835": "Ressources Humaines",
                    "44|101817": ".....Administration des RH",
                    "45|101818": ".....Développement des RH",
                    "46|101819": ".....Direction des ressources humaines",
                    "47|101820": ".....Formation initiale et continue",
                    "48|101836": "Sanitaire, Social, Culture",
                    "49|101821": ".....Activités sanitaires, sociales et culturelles",
                    "50|101837": "Services Techniques",
                    "51|101822": ".....Achats",
                    "52|101823": ".....Direction des services techniques",
                    "53|101824": ".....Logistique",
                    "54|101825": ".....Maintenance, sécurité",
                    "55|101826": ".....Process, méthodes",
                    "56|101827": ".....Qualité",
                }.items()
            )
        ]
    )

    secteur_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "-- Indifférent --",
                    "101752": "Activités des organisations associatives et administration publique",
                    "101753": "Activités informatiques",
                    "101754": "Activités juridiques et comptables",
                    "101755": "Agroalimentaire",
                    "101756": "Automobile, aéronautique et autres matériels de transport",
                    "101757": "Banque et Assurances",
                    "101758": "Bois - Papier - Imprimerie",
                    "101759": "Chimie - Caoutchouc - Plastique",
                    "101760": "Commerce interentreprises",
                    "101761": "Communication et médias",
                    "101762": "Conseil et gestion des entreprises",
                    "101763": "Construction",
                    "101764": "Distribution généraliste et spécialisée",
                    "101765": "Energies - Eau",
                    "101766": "Equipements électriques et électroniques",
                    "101767": "Formation initiale et continue",
                    "101768": "Gestion des déchets",
                    "101769": "Hôtellerie - Restauration - Loisirs",
                    "101770": "Immobilier",
                    "101771": "Industrie pharmaceutique",
                    "101772": "Ingénierie - R et D",
                    "101773": "Intermédiaires du recrutement",
                    "101774": "Mécanique - Métallurgie",
                    "101775": "Meuble, Textile et autres industries manufacturières",
                    "101776": "Santé - action sociale",
                    "101777": "Services divers aux entreprises",
                    "101778": "Télécommunications",
                    "101779": "Transports et logistique",
                }.items()
            )
        ]
    )

    type_contrat_choices = OrderedDict([(k, "%s" % (v)) for k, v in sorted(APEC_CONTRATS.items())])

    salary_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "-- Indifférent --",
                    "0|35": "Moins de 35 K€",
                    "35|50": "Entre 35 et 49 K€",
                    "50|70": "Entre 50 et 69 K€",
                    "70|90": "Entre 70 et 90 K€",
                    "90|1000": "Plus de 90 K€",
                }.items()
            )
        ]
    )

    date_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    " ": "-- Indifférent --",
                    "101850": "Aujourd'hui",
                    "101851": "Les 7 derniers jours",
                    "101852": "Les 30 derniers jours",
                    "101853": "Toutes les offres",
                }.items()
            )
        ]
    )

    level_choices = OrderedDict([(k, "%s" % (v)) for k, v in sorted(APEC_EXPERIENCE.items())])

    CONFIG = BackendConfig(
        Value("place", label="Lieu", choices=places_choices, default=""),
        Value("fonction", label="Fonction", choices=fonction_choices, default=""),
        Value("secteur", label="Secteur", choices=secteur_choices, default=""),
        Value("contrat", label="Contrat", choices=type_contrat_choices, default=""),
        Value("salaire", label="Salaire", choices=salary_choices, default=""),
        Value("limit_date", label="Date", choices=date_choices, default=""),
        Value("level", label="Expérience", choices=level_choices, default=""),
    )

    def search_job(self, pattern=None):
        for job_advert in self.browser.search_job(pattern=pattern):
            yield self.fill_obj(job_advert)

    def decode_choice(self, choice):
        splitted_choice = choice.split("|")
        if len(splitted_choice) == 2:
            return splitted_choice[1]
        else:
            return ""

    def advanced_search_job(self):
        for job_advert in self.browser.advanced_search_job(
            region=self.decode_choice(self.config["place"].get()),
            fonction=self.decode_choice(self.config["fonction"].get()),
            secteur=self.config["secteur"].get(),
            salaire=self.config["salaire"].get(),
            contrat=self.config["contrat"].get(),
            limit_date=self.config["limit_date"].get(),
            level=self.config["level"].get(),
        ):
            yield self.fill_obj(job_advert)

    def get_job_advert(self, _id, advert=None):
        job_advert = self.browser.get_job_advert(_id, advert)
        return self.fill_obj(job_advert)

    def fill_obj(self, advert, fields=None):
        if advert.contract_type in self.type_contrat_choices:
            advert.contract_type = self.type_contrat_choices[advert.contract_type]

        if advert.experience in self.level_choices:
            advert.experience = self.level_choices[advert.experience]

        return advert

    OBJECTS = {BaseJobAdvert: fill_obj}
