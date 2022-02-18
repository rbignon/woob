# -*- coding: utf-8 -*-

# Copyright(C) 2009-2019  Romain Bignon
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

import re
from urllib.parse import urlencode

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import Format, Date, Env, Field
from woob.browser.pages import JsonPage, LoggedPage, RawPage
from woob.capabilities.bill import Document, Bill, DocumentTypes

from .pages import ErrorPage

patterns = {
    r'Relevé': DocumentTypes.STATEMENT,
    r'Livret(s) A': DocumentTypes.STATEMENT,
    r'développement durable': DocumentTypes.STATEMENT,
    r'Synthèse': DocumentTypes.STATEMENT,
    r'Echelles/Décomptes': DocumentTypes.STATEMENT,
    r'épargne logement': DocumentTypes.STATEMENT,
    r'Livret(s) jeune': DocumentTypes.STATEMENT,
    r'Compte(s) sur Livret': DocumentTypes.STATEMENT,
    r'Récapitulatifs annuels': DocumentTypes.REPORT,
    r"Avis d'exécution": DocumentTypes.REPORT,
    r'Factures': DocumentTypes.BILL,
}


def get_document_type(family):
    for patt, type in patterns.items():
        if re.search(re.escape(patt), family):
            return type
    return DocumentTypes.OTHER


class TitulairePage(LoggedPage, JsonPage):
    pass


class ItemDocument(ItemElement):
    def build_object(self):
        if Field('type')(self) == DocumentTypes.BILL:
            return Bill()
        return Document()

    def condition(self):
        # There is two type of json, the one with the ibancrypte in it
        # and the one with the idcontrat in it, here we check if
        # the document belong to the subscription.
        if 'ibanCrypte' in self.el:
            return Env('sub_id')(self) in Dict('ibanCrypte')(self)
        return Env('sub_number')(self) in Dict('numeroCompteAnonymise', default='')(self)

    obj_date = Date(Dict('dateDoc'), dayfirst=True)
    obj_format = 'pdf'
    obj_id = Format('%s_%s', Env('sub_id'), Dict('idDoc'))

    def obj_label(self):
        if 'ibanCrypte' in self.el:
            return '%s %s N° %s' % (
                Dict('dateDoc')(self),
                Dict('libelleSousFamille')(self),
                Dict('numeroCompteAnonymise')(self),
            )
        else:
            return '%s %s N° %s' % (Dict('dateDoc')(self), Dict('libelleSousFamille')(self), Dict('idContrat')(self))

    def obj_url(self):
        keys_to_copy = {
            'idDocument': 'idDoc',
            'dateDocument': 'dateDoc',
            'idLocalisation': 'idLocalisation',
            'viDocDocument': 'viDocDocument',
        }
        # Here we parse the json with ibancrypte in it, for most cases
        if 'ibanCrypte' in self.el:
            url = 'demat-wspl/rest/consultationDocumentDemat?'
            keys_to_copy.update({
                'typeCpt': 'typeCompte',
                'familleDoc': 'famDoc',
                'ibanCrypte': 'ibanCrypte',
                'typeDoc': 'typeDoc',
                'consulted': 'consulted',
            })
            request_params = {'typeFamille': 'R001', 'ikpiPersonne': ''}
        # Here we parse the json with idcontrat in it. For the cases present
        # on privee.mabanque where sometimes the doc url is different
        else:
            url = 'demat-wspl/rest/consultationDocumentSpecialBpfDemat?'
            keys_to_copy.update({
                'heureDocument': 'heureDoc',
                'numClient': 'numClient',
                'typeReport': 'typeReport',
            })
            request_params = {'ibanCrypte': ''}

        for k, v in keys_to_copy.items():
            request_params[k] = Dict(v)(self)

        return Env('baseurl')(self) + url + urlencode(request_params)

    def obj_type(self):
        return get_document_type(Dict('libelleSousFamille')(self))


class DocumentsPage(LoggedPage, ErrorPage):
    @method
    class iter_documents(DictElement):
        # * refer to the account, it can be 'Comptes chèques', 'Comptes d'épargne', etc...
        item_xpath = 'data/listerDocumentDemat/mapReleves/*/listeDocument'
        ignore_duplicate = True

        class item(ItemDocument):
            pass

    @method
    class iter_documents_pro(DictElement):
        # * refer to the account, it can be 'Comptes chèques', 'Comptes d'épargne', etc...
        item_xpath = 'data/listerDocumentDemat/mapRelevesPro/*/listeDocument'
        ignore_duplicate = True

        class item(ItemDocument):
            pass


class RIBPage(LoggedPage, RawPage):
    def is_rib_available(self):
        # If the page has no content, it means no RIB can be found
        return bool(self.content)
