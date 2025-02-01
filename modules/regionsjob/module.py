# Copyright(C) 2014      Bezleputh
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

from .browser import RegionsjobBrowser


__all__ = ["RegionsjobModule"]


class RegionsjobModule(Module, CapJob):
    NAME = "regionsjob"
    DESCRIPTION = "regionsjob website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    BROWSER = RegionsjobBrowser

    website_choices = OrderedDict(
        [
            (k, f"{v} ({k})")
            for k, v in sorted(
                {
                    "www.centrejob.com": "CentreJob",
                    "www.estjob.com": "EstJob",
                    "www.nordjob.com": "NordJob",
                    "www.ouestjob.com": "OuestJob",
                    "www.pacajob.com": "PacaJob",
                    "www.parisjob.com": "ParisJob",
                    "www.rhonealpesjob.com": "RhoneAlpesJob",
                    "www.sudouestjob.com": "SudOuestJob",
                    "www.jobtrotter.com": "JobTrotter",
                }.items()
            )
        ]
    )

    fonction_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "Indifferent",
                    "Assistanat_admin_accueil": "Assistanat/Adm.ventes/Accueil",
                    "BTP_gros_second_oeuvre": "BTP - Gros Oeuvre/Second Oeuvre",
                    "Bureau_etude_R_D": "Bureau d'Etudes/R & D/BTP archi/conception",
                    "Commercial_technico_com": "Commercial - Technico-Commercial",
                    "Commercial_particulier": "Commercial auprès des particuliers",
                    "Commercial_professionnel": "Commercial auprès des professionnels",
                    "Commercial_vendeur": "Commercial-Vendeur en magasin",
                    "Compta_gestion_finance_audit": "Compta/Gestion/Finance/Audit",
                    "Dir_resp_centre_profit": "Direction/Resp. Co. et Centre de Profit",
                    "Import_export_inter": "Import/Export/International",
                    "Informatique_dev_hard": "Informatique - Dével. Hardware",
                    "Informatique_dev": "Informatique - Développement",
                    "Informatique_syst_info": "Informatique - Systèmes d'Information",
                    "Informatique_syst_reseaux": "Informatique - Systèmes/Réseaux",
                    "Ingenierie_agro_agri": "Ingénierie - Agro/Agri",
                    "Ingenierie_chimie_pharma_bio": "Ingénierie - Chimie/Pharmacie/Bio.",
                    "Ingenierie_electro_tech": "Ingénierie - Electro-tech./Automat.",
                    "Ingenierie_meca_aero": "Ingénierie - Mécanique/Aéron.",
                    "Ingenierie_telecom": "Ingénierie - Telecoms/Electronique",
                    "Juridique_droit": "Juridique/Droit",
                    "Logistique_metiers_transport": "Logistique/Métiers du Transport",
                    "Marketing_com_graphisme": "Marketing/Communication/Graphisme",
                    "Dir_management_resp": "Métiers de la distribution - Management/Resp.",
                    "Metiers_fonction_publique": "Métiers de la Fonction Publique",
                    "Negociation_gest_immo": "Négociation/Gestion immobilière",
                    "Production_gestion": "Production - Gestion/Maintenance",
                    "Production_operateur": "Production - Opérateur/Manoeuvre",
                    "Qualite_securite_environnement": "Qualité/Hygiène/Sécurité/Environnement",
                    "Restauration_hotellerie_tourisme": "Restauration/Tourisme/Hôtellerie/Loisirs",
                    "RH_Personnel_Formation": "RH/Personnel/Formation",
                    "Sante_social": "Santé/Social",
                    "SAV_Hotline": "SAV/Hotline/Téléconseiller",
                    "Services_pers_entreprises": "Services à la personne/aux entreprises",
                }.items()
            )
        ]
    )

    secteur_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "Indifferent",
                    "Agri_peche": "Agriculture/Pêche",
                    "Banq_assur_finan": "Banque/Assurance/Finance",
                    "BTP": "BTP",
                    "Distrib_commerce": "Distribution/Commerce de gros",
                    "Enseign_forma": "Enseignement/Formation",
                    "Immo": "Immobilier",
                    "Ind_aero": "Industrie Aéronautique/Aérospatial",
                    "Ind_agro": "Industrie Agro-alimentaire",
                    "Ind_auto_meca_nav": "Industrie Auto/Meca/Navale",
                    "Ind_hightech_telecom": "Industrie high-tech/Telecom",
                    "Ind_manufact": "Industrie Manufacturière",
                    "Ind_petro": "Industrie Pétrolière/Pétrochimie",
                    "Ind_pharma_bio_chim": "Industrie Pharmaceutique/Biotechn./Chimie",
                    "Media_internet_com": "Média/Internet/Communication",
                    "Resto": "Restauration",
                    "Sante_social": "Santé/Social/Association",
                    "Energie_envir": "Secteur Energie/Environnement",
                    "Inform_SSII": "Secteur informatique/SSII",
                    "Serv_public_autre": "Service public autres",
                    "Serv_public_collec_terri": "Service public des collectivités territoriales",
                    "Serv_public_etat": "Service public d'état",
                    "Serv_public_hosp": "Service public hospitalier",
                    "Serv_entreprise": "Services aux Entreprises",
                    "Serv_pers_part": "Services aux Personnes/Particuliers",
                    "Tourism_hotel_loisir": "Tourisme/Hôtellerie/Loisirs",
                    "Transport_logist": "Transport/Logistique",
                }.items()
            )
        ]
    )

    experience_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "      ": "Indifferent",
                    "Inf_1": "- 1 an",
                    "1_7": "1 à 7 ans",
                    "Sup_7": "+ 7 ans",
                }.items()
            )
        ]
    )

    contract_choices = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "Tous types de contrat",
                    "CDD": "CDD",
                    "CDI": "CDI",
                    "Stage": "Stage",
                    "Travail_temp": "Travail temporaire",
                    "Alternance": "Alternance",
                    "Independant": "Indépendant",
                    "Franchise": "Franchise",
                }.items()
            )
        ]
    )

    qualification_choice = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "Indifferent",
                    "BEP_CAP": "BEP/CAP",
                    "Employe_Operateur": "Employé/Opérateur/Ouvrier Spe/Bac",
                    "Technicien_B2": "Technicien/Employé Bac +2",
                    "Agent_maitrise_B3": "Agent de maîtrise/Bac +3/4",
                    "Ingenieur_B5": "Ingénieur/Cadre/Bac +5",
                    "Cadre_dirigeant": "> Bac + 5 (cadre dirigeant)",
                }.items()
            )
        ]
    )

    enterprise_type_choice = OrderedDict(
        [
            (k, "%s" % (v))
            for k, v in sorted(
                {
                    "": "Tous types d'entreprises",
                    "Cabinet_recr": "Cabinets de recrutement",
                    "Entreprises": "Entreprises",
                    "SSII": "SSII",
                    "Travail_temporaire": "Travail temporaire",
                }.items()
            )
        ]
    )

    CONFIG = BackendConfig(
        Value("website", label="Region", choices=website_choices),
        Value("place", label="Place", masked=False, default=""),
        Value("metier", label="Job name", masked=False, default=""),
        Value("fonction", label="Fonction", choices=fonction_choices, default=""),
        Value("secteur", label="Secteur", choices=secteur_choices, default=""),
        Value("contract", label="Contract", choices=contract_choices, default=""),
        Value("experience", label="Experience", choices=experience_choices, default=""),
        Value("qualification", label="Qualification", choices=qualification_choice, default=""),
        Value("enterprise_type", label="Enterprise type", choices=enterprise_type_choice, default=""),
    )

    def create_default_browser(self):
        return self.create_browser(self.config["website"].get())

    def search_job(self, pattern=""):
        return self.browser.search_job(pattern=pattern)

    def advanced_search_job(self):
        return self.browser.search_job(
            pattern=self.config["metier"].get(),
            fonction=self.config["fonction"].get(),
            secteur=self.config["secteur"].get(),
            contract=self.config["contract"].get(),
            experience=self.config["experience"].get().strip(),
            qualification=self.config["qualification"].get(),
            enterprise_type=self.config["enterprise_type"].get(),
            place=self.config["place"].get(),
        )

    def get_job_advert(self, _id, advert=None):
        return self.browser.get_job_advert(_id, advert)

    def fill_obj(self, advert, fields):
        return self.get_job_advert(advert.id, advert)

    OBJECTS = {BaseJobAdvert: fill_obj}
