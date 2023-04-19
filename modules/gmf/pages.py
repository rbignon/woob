# Copyright(C) 2017      Tony Malto
#
# flake8: compatible
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

import re

from woob.browser.pages import FormNotFound, HTMLPage, JsonPage, LoggedPage, XMLPage
from woob.browser.elements import DictElement, ItemElement, method, ListElement, TableElement
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Currency, Date, Eval, Field, Regexp,
)
from woob.browser.filters.html import Attr, TableCell
from woob.browser.filters.json import Dict
from woob.capabilities.base import empty, NotAvailable
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.exceptions import ActionNeeded, ActionType


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'Versement'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'Arbitrage'), FrenchTransaction.TYPE_ORDER),
    ]


class LoginPage(JsonPage):
    def get_id(self):
        return self.doc['identifiantTechnique']

    def get_status(self):
        return self.doc['statut']


class RedirectionPage(HTMLPage):
    pass


class AuthCodePage(LoggedPage, JsonPage):
    def get_csrf_token(self):
        return self.doc['csrf']


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):

        class item(ItemElement):
            klass = Account

            def condition(self):
                return Dict('gamme')(self) == 'EPARGNE'

            obj_id = CleanText(Dict('numContrat'))
            obj_label = CleanText(Dict('labelContrat'))
            obj_type = Account.TYPE_LIFE_INSURANCE
            obj_balance = CleanDecimal.French(Dict('mttValeurAcquise'))
            obj_currency = Currency(Dict('mttValeurAcquise'))
            obj_opening_date = Date(
                CleanText(Dict('dateEffet')),
                dayfirst=True,
                default=NotAvailable,
            )

    def get_details_page_form_data(self, account):
        for product in self.doc:
            if product['numContrat'] == account.id:
                return {
                    'REF_INT_CONTRAT': product['refInterne'],
                    'PRODUIT': product['codeProduit'],
                    'LABEL_PRODUIT': product.get('labelProduit') or '',
                    'CODE_GAMME': product['codeGamme'],
                    'ONG_PRESEL': '',
                    'DATE_EFFET': product.get('dateEffet') or '',
                    'REF_EXT_CONTRAT': product['refExterne'],
                    'CLEFS_REF_EXT_CONTRAT': product['cleRefExterne'],
                    'GROUPE_PRODUIT': product['codeGroupe'],
                    'NB_RISQUES_HABITATION': product['nbRisqueHabitation'],
                    'TYPE_RISQUE': product.get('typeRisque') or '',
                }


class InvestmentsParser(TableElement):
    col_label = 'Support'
    col_share = 'Répartition en %'
    col_valuation = 'Montant'
    col_unitvalue = "Valeur de l'unité de compte"

    class item(ItemElement):
        klass = Investment

        obj_label = CleanText(TableCell('label'))
        obj_portfolio_share = Eval(lambda x: x / 100, CleanDecimal(TableCell('share'), replace_dots=True))
        obj_valuation = CleanDecimal(TableCell('valuation'), replace_dots=True)
        obj_unitvalue = CleanDecimal(TableCell('unitvalue'), replace_dots=True, default=NotAvailable)
        obj_quantity = CleanDecimal(TableCell('quantity'), default=NotAvailable)


class TransactionsParser(object):
    @method
    class iter_history(ListElement):
        item_xpath = '//div[contains(@id, "listeMouvements")]/table//tr[position()>1]'

        class item(ItemElement):
            klass = Transaction

            obj_rdate = obj_date = Date(CleanText('./td[1]'))
            obj_raw = Transaction.Raw('./td[2]')
            obj_amount = CleanDecimal('./td[3]', replace_dots=True)
            obj__detail_id = Regexp(
                Attr('./td[4]/a', 'href', default=NotAvailable),
                r'popin(\d+)',
                default=NotAvailable
            )

            def obj_investments(self):
                detail_id = Field('_detail_id')(self)
                if empty(detail_id):
                    return NotAvailable
                investment_details = self.page.doc.xpath('//div[@id="popin{}"]'.format(detail_id))
                assert len(investment_details) == 1
                return list(self.get_investments(self.page, el=investment_details[0]))

            class get_investments(InvestmentsParser):
                item_xpath = './p[strong[contains(text(), "Répartition de votre versement") or contains(text(), "Réinvestissement") or contains(text(), "Désinvestissement")]]/following-sibling::table//tr[position()>1]'
                head_xpath = './p[strong[contains(text(), "Répartition de votre versement") or contains(text(), "Réinvestissement") or contains(text(), "Désinvestissement")]]/following-sibling::table//tr[1]/th'
                col_quantity = re.compile("Nombre")  # use regex because the column name tends to be inconsistent between the tables


class TransactionsInvestmentsPage(LoggedPage, HTMLPage, TransactionsParser):
    def show_all_transactions(self):
        # show all transactions if many of them
        if self.doc.xpath('//span[contains(text(), "Plus de mouvements financiers")]'):
            try:
                form = self.get_form(name="formStep1")

                # have a look to the javascript file called 'jsf.js.faces' and
                # to the js listener "mojarra.ab" to understand
                # All parameters can be hardcoded
                form['javax.faces.source'] = 'formStep1:tabOnglets:plusDeMouvementFinancier'
                form['javax.faces.partial.event'] = 'click'
                form['javax.faces.partial.execute'] = 'formStep1:tabOnglets:plusDeMouvementFinancier'
                form['javax.faces.partial.render'] = 'formStep1:tabOnglets:listeMouvements formStep1:tabOnglets:gPlusDeMouvementFinancier formStep1:tabOnglets:gMoinsDeMouvementFinancier formStep1:tabOnglets:listPopinMouvement'
                form['javax.faces.behavior.event'] = 'click'
                form['javax.faces.partial.ajax'] = "true"

                form.submit()
            except FormNotFound:
                pass

    def has_investments(self):
        if self.doc.xpath('//li/a[text()="Portefeuille"]'):
            return True

    @method
    class iter_investments(InvestmentsParser):
        item_xpath = '//div[h3[normalize-space()="Répartition de votre portefeuille"]]//table//tr[position()>1]'
        head_xpath = '//div[h3[normalize-space()="Répartition de votre portefeuille"]]//table//tr[1]/th'
        col_quantity = "Nombre d'unités de comptes"


class AllTransactionsPage(LoggedPage, XMLPage, HTMLPage, TransactionsParser):
    def build_doc(self, content):
        # HTML embedded in XML: parse XML first then extract the html
        xml = XMLPage.build_doc(self, content)
        transactions_html = (xml.xpath('//partial-response/changes/update[1]')[0].text
                             .encode(encoding=self.encoding))
        investments_html = (xml.xpath('//partial-response/changes/update[2]')[0].text
                            .encode(encoding=self.encoding))
        html = transactions_html + investments_html
        return HTMLPage.build_doc(self, html)


class DocumentsSignaturePage(LoggedPage, HTMLPage):
    def on_load(self):
        if self.doc.xpath('//span[contains(text(), "VO(S) DOCUMENT(S) A SIGNER")]'):
            raise ActionNeeded(
                locale="fr-FR",
                message=CleanText(
                    '//div[@class="block"]/p[contains(text(), "Vous avez un ou plusieurs document(s) à signer")]'
                )(self.doc),
                action_type=ActionType.ACKNOWLEDGE,
            )


class RedirectToUserAgreementPage(LoggedPage, HTMLPage):
    MAX_REFRESH = 0


class UserAgreementPage(LoggedPage, HTMLPage):
    def on_load(self):
        message = CleanText('//fieldset//legend|//fieldset//label')(self.doc)
        if 'conditions générales' in message:
            raise ActionNeeded(locale="fr-FR", message=message, action_type=ActionType.ACKNOWLEDGE)
