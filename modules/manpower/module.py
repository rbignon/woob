# -*- coding: utf-8 -*-

# Copyright(C) 2016      Bezleputh
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

from .browser import ManpowerBrowser


__all__ = ["ManpowerModule"]


class ManpowerModule(Module, CapJob):
    NAME = "manpower"
    DESCRIPTION = "manpower website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    BROWSER = ManpowerBrowser

    type_contract_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "All",
                    "cdi-interimaire/c11": "Autre",
                    "formation-en-alternance/c4": "Alternance",
                    "interim/c1": "CDD",
                    "cdd/c2": "CDI",
                    "cdi/c3": "Mission en intérim",
                }.items()
            )
        ]
    )

    activityDomain_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "All",
                    "accueil-secretariat/s69": "Accueil - Secrétariat",
                    "achats-commerce-distribution/s66": "Achats - Commerce - Distribution",
                    "agro-alimentaire/s65": "Agro-Alimentaire",
                    "automobile/s2": "Automobile",
                    "banque-assurances-immobilier/s3": "Banque - Assurances - Immobilier",
                    "bijoux-horlogerie-lunetterie/s61": "Bijoux - Horlogerie - Lunetterie",
                    "bureau-d-etudes-methodes-qualite/s4": "Bureau d'études- Méthodes - Qualité",
                    "chimie-pharmacie-cosmetologie/s6": "Chimie - Pharmacie - Cosmétologie",
                    "communication/s73": "Communication",
                    "comptabilite-finance/s62": "Comptabilité - Finance",
                    "construction-travaux-publics/s9": "Construction - Travaux publics",
                    "electricite-electronique/s67": "Electricité - Electronique",
                    "environnement-developpement-durable/s80": "Environnement - Développement Durable",
                    "hotellerie-restauration-tourisme/s24": "Hôtellerie- Restauration - Tourisme",
                    "it-commercial-conseil-amoa/s75": "IT - Commercial - Conseil - AMOA",
                    "it-etude-et-developpement/s14": "IT - Etude et Développement",
                    "it-exploitation-systeme-sgbd/s76": "IT - Exploitation - Système - SGBD",
                    "it-reseau-telecom/s77": "IT - Réseau - Telecom",
                    "it-support-maintenance-help-desk/s78": "IT - Support - Maintenance - Help Desk",
                    "imprimerie/s12": "Imprimerie",
                    "industrie-aeronautique/s79": "Industrie aéronautique",
                    "logistique/s70": "Logistique",
                    "maintenance-entretien/s53": "Maintenance - Entretien",
                    "multimedia/s74": "Multimédia",
                    "metallurgie-fonderie/s49": "Métallurgie- Fonderie",
                    "naval/s47": "Naval",
                    "nucleaire-autres-energies/s54": "Nucléaire - Autres Énergies",
                    "papier-carton/s20": "Papier - Carton",
                    "plasturgie/s22": "Plasturgie",
                    "production-graphique/s72": "Production Graphique",
                    "production-industrielle-mecanique/s16": "Production industrielle - Mécanique",
                    "ressources-humaines-juridique/s63": "Ressources humaines - Juridique",
                    "sante/s25": "Santé",
                    "spectacle/s71": "Spectacle",
                    "surveillance-securite/s68": "Surveillance - Sécurité",
                    "textile-couture-cuir/s26": "Textile - Couture - Cuir",
                    "transport/s64": "Transport",
                    "transport-aerien/s52": "Transport aérien",
                    "teleservices-marketing-vente/s21": "Téléservices - Marketing - Vente",
                    "verre-porcelaine/s48": "Verre - Porcelaine",
                    "vin-agriculture-paysagisme/s60": "Vin - Agriculture - Paysagisme",
                }.items()
            )
        ]
    )

    places_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "All",
                    "alsace/r01": "Alsace",
                    "alsace/bas-rhin/r01d67": "Bas-Rhin",
                    "alsace/haut-rhin/r01d68": "Haut-Rhin",
                    "aquitaine/r02": "Aquitaine",
                    "aquitaine/dordogne/r02d24": "Dordogne",
                    "aquitaine/gironde/r02d33": "Gironde",
                    "aquitaine/landes/r02d40": "Landes",
                    "aquitaine/lot-et-garonne/r02d47": "Lot-et-Garonne",
                    "aquitaine/pyrenees-atlantiques/r02d64": "Pyrénées-Atlantiques",
                    "auvergne/r03": "Auvergne",
                    "auvergne/allier/r03d3": "Allier",
                    "auvergne/cantal/r03d15": "Cantal",
                    "auvergne/haute-loire/r03d43": "Haute-Loire",
                    "auvergne/puy-de-dome/r03d63": "Puy-de-Dôme",
                    "basse-normandie/r04": "Basse-Normandie",
                    "basse-normandie/calvados/r04d14": "Calvados",
                    "basse-normandie/manche/r04d50": "Manche",
                    "basse-normandie/orne/r04d61": "Orne",
                    "bourgogne/r05": "Bourgogne",
                    "bourgogne/cote-d-or/r05d21": "Côte-d'Or",
                    "bourgogne/nievre/r05d58": "Nièvre",
                    "bourgogne/saone-et-loire/r05d71": "Saône-et-Loire",
                    "bourgogne/yonne/r05d89": "Yonne",
                    "bretagne/r06": "Bretagne",
                    "bretagne/cotes-d-armor/r06d22": "Côtes-d'Armor",
                    "bretagne/finistere/r06d29": "Finistère",
                    "bretagne/ille-et-vilaine/r06d35": "Ille-et-Vilaine",
                    "bretagne/morbihan/r06d56": "Morbihan",
                    "centre/r07": "Centre",
                    "centre/cher/r07d18": "Cher",
                    "centre/eure-et-loir/r07d28": "Eure-et-Loir",
                    "centre/indre/r07d36": "Indre",
                    "centre/indre-et-loire/r07d37": "Indre-et-Loire",
                    "centre/loir-et-cher/r07d41": "Loir-et-Cher",
                    "centre/loiret/r07d45": "Loiret",
                    "champagne-ardennes/r08": "Champagne-Ardennes",
                    "champagne-ardennes/ardennes/r08d8": "Ardennes",
                    "champagne-ardennes/aube/r08d10": "Aube",
                    "champagne-ardennes/haute-marne/r08d52": "Haute-Marne",
                    "champagne-ardennes/marne/r08d51": "Marne",
                    "dom-tom/r23": "Dom Tom",
                    "dom-tom/nouvelle-caledonie/r23d98": "Nouvelle Calédonie",
                    "franche-comte/r10": "Franche-Comté",
                    "franche-comte/doubs/r10d25": "Doubs",
                    "franche-comte/haute-saone/r10d70": "Haute-Saône",
                    "franche-comte/jura/r10d39": "Jura",
                    "franche-comte/territoire-de-belfort/r10d90": "Territoire de Belfort",
                    "haute-normandie/r11": "Haute-Normandie",
                    "haute-normandie/eure/r11d27": "Eure",
                    "haute-normandie/seine-maritime/r11d76": "Seine-Maritime",
                    "ile-de-france/r12": "Île-de-France",
                    "ile-de-france/essonne/r12d91": "Essonne",
                    "ile-de-france/hauts-de-seine/r12d92": "Hauts-de-Seine",
                    "ile-de-france/paris/r12d75": "Paris",
                    "ile-de-france/seine-st-denis/r12d93": "Seine-St-Denis",
                    "ile-de-france/seine-et-marne/r12d77": "Seine-et-Marne",
                    "ile-de-france/val-d-oise/r12d95": "Val-d'Oise",
                    "ile-de-france/val-de-marne/r12d94": "Val-de-Marne",
                    "ile-de-france/yvelines/r12d78": "Yvelines",
                    "languedoc-roussillon/r13": "Languedoc-Roussillon",
                    "languedoc-roussillon/aude/r13d11": "Aude",
                    "languedoc-roussillon/gard/r13d30": "Gard",
                    "languedoc-roussillon/herault/r13d34": "Hérault",
                    "languedoc-roussillon/lozere/r13d48": "Lozère",
                    "languedoc-roussillon/pyrenees-orientales/r13d66": "Pyrénées-Orientales",
                    "limousin/r14": "Limousin",
                    "limousin/correze/r14d19": "Corrèze",
                    "limousin/creuse/r14d23": "Creuse",
                    "limousin/haute-vienne/r14d87": "Haute-Vienne",
                    "lorraine/r15": "Lorraine",
                    "lorraine/meurthe-et-moselle/r15d54": "Meurthe-et-Moselle",
                    "lorraine/meuse/r15d55": "Meuse",
                    "lorraine/moselle/r15d57": "Moselle",
                    "lorraine/vosges/r15d88": "Vosges",
                    "midi-pyrenees/r16": "Midi-Pyrénées",
                    "midi-pyrenees/ariege/r16d9": "Ariège",
                    "midi-pyrenees/aveyron/r16d12": "Aveyron",
                    "midi-pyrenees/gers/r16d32": "Gers",
                    "midi-pyrenees/haute-garonne/r16d31": "Haute-Garonne",
                    "midi-pyrenees/hautes-pyrenees/r16d65": "Hautes-Pyrénées",
                    "midi-pyrenees/lot/r16d46": "Lot",
                    "midi-pyrenees/tarn/r16d81": "Tarn",
                    "midi-pyrenees/tarn-et-garonne/r16d82": "Tarn-et-Garonne",
                    "nord-pas-de-calais/r17": "Nord-Pas-de-Calais",
                    "nord-pas-de-calais/nord/r17d59": "Nord",
                    "nord-pas-de-calais/pas-de-calais/r17d62": "Pas-de-Calais",
                    "pays-de-la-loire/r19": "Pays de la Loire",
                    "pays-de-la-loire/loire-atlantique/r19d44": "Loire-Atlantique",
                    "pays-de-la-loire/maine-et-loire/r19d49": "Maine-et-Loire",
                    "pays-de-la-loire/mayenne/r19d53": "Mayenne",
                    "pays-de-la-loire/sarthe/r19d72": "Sarthe",
                    "pays-de-la-loire/vendee/r19d85": "Vendée",
                    "picardie/r20": "Picardie",
                    "picardie/aisne/r20d2": "Aisne",
                    "picardie/oise/r20d60": "Oise",
                    "picardie/somme/r20d80": "Somme",
                    "poitou-charentes/r21": "Poitou-Charentes",
                    "poitou-charentes/charente/r21d16": "Charente",
                    "poitou-charentes/charente-maritime/r21d17": "Charente-Maritime",
                    "poitou-charentes/deux-sevres/r21d79": "Deux-Sèvres",
                    "poitou-charentes/vienne/r21d86": "Vienne",
                    "provence-alpes-cote-d-azur/r18": "Provence-Alpes-Côte d'Azur",
                    "provence-alpes-cote-d-azur/alpes-maritimes/r18d6": "Alpes-Maritimes",
                    "provence-alpes-cote-d-azur/alpes-de-haute-provence/r18d4": "Alpes-de-Haute-Provence",
                    "provence-alpes-cote-d-azur/bouches-du-rhone/r18d13": "Bouches-du-Rhône",
                    "provence-alpes-cote-d-azur/hautes-alpes/r18d5": "Hautes-Alpes",
                    "provence-alpes-cote-d-azur/var/r18d83": "Var",
                    "provence-alpes-cote-d-azur/vaucluse/r18d84": "Vaucluse",
                    "rhone-alpes/r22": "Rhône-Alpes",
                    "rhone-alpes/ain/r22d1": "Ain",
                    "rhone-alpes/ardeche/r22d7": "Ardèche",
                    "rhone-alpes/drome/r22d26": "Drôme",
                    "rhone-alpes/haute-savoie/r22d74": "Haute-Savoie",
                    "rhone-alpes/isere/r22d38": "Isère",
                    "rhone-alpes/loire/r22d42": "Loire",
                    "rhone-alpes/rhone/r22d69": "Rhône",
                    "rhone-alpes/savoie/r22d73": "Savoie",
                }.items()
            )
        ]
    )

    CONFIG = BackendConfig(
        Value("job", label="Job name", masked=False, default=""),
        Value("place", label="County", choices=places_choices, default=""),
        Value("contract", labe="Contract type", choices=type_contract_choices, default=""),
        Value("activity_domain", label="Activity Domain", choices=activityDomain_choices, default=""),
    )

    def advanced_search_job(self):
        for advert in self.browser.advanced_search_job(
            job=self.config["job"].get(),
            place=self.config["place"].get(),
            contract=self.config["contract"].get(),
            activity_domain=self.config["activity_domain"].get(),
        ):
            yield advert

    def get_job_advert(self, _id, advert=None):
        return self.browser.get_job_advert(_id, advert)

    def search_job(self, pattern=None):
        for advert in self.browser.search_job(pattern):
            yield advert

    def fill_obj(self, advert, fields):
        return self.get_job_advert(advert.id, advert)

    OBJECTS = {BaseJobAdvert: fill_obj}
