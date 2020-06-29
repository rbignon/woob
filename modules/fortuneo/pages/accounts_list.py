# -*- coding: utf-8 -*-

# Copyright(C) 2012 Gilles-Alexandre Quenot
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re
import sys
from datetime import date

from dateutil.relativedelta import relativedelta

from weboob.browser.elements import method, ItemElement, TableElement, ListElement
from weboob.browser.filters.html import Link, Attr, AbsoluteLink, TableCell
from weboob.browser.filters.standard import (
    CleanText, CleanDecimal, Regexp, Date, Currency, Base, Field, MapIn,
)
from weboob.capabilities import NotAvailable
from weboob.capabilities.bank import Account, AccountOwnership
from weboob.capabilities.wealth import Investment, MarketOrder, MarketOrderDirection, MarketOrderType
from weboob.capabilities.profile import Person
from weboob.browser.pages import HTMLPage, LoggedPage, FormNotFound, CsvPage
from weboob.tools.capabilities.bank.transactions import FrenchTransaction
from weboob.tools.capabilities.bank.investments import IsinCode, IsinType
from weboob.tools.date import parse_french_date
from weboob.exceptions import ActionNeeded


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(?P<category>CHEQUE)(?P<text>.*)'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(?P<category>FACTURE CARTE) DU (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}) (?P<text>.*?)( CA?R?T?E? ?\d*X*\d*)?$'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^(?P<category>CARTE)( DU)? (?P<dd>\d{2})/(?P<mm>\d{2}) (?P<text>.*)'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^(?P<category>(PRELEVEMENT|TELEREGLEMENT|TIP|PRLV)) (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(?P<category>ECHEANCEPRET)(?P<text>.*)'), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r'^(?P<category>RET(RAIT)? DAB) (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})( (?P<HH>\d+)H(?P<MM>\d+))? (?P<text>.*)'), FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r'^(?P<category>VIR(EMEN)?T? ((RECU|FAVEUR) TIERS|SEPA RECU)?)( /FRM)?(?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^(?P<category>REMBOURST)(?P<text>.*)'), FrenchTransaction.TYPE_PAYBACK),
        (re.compile(r'^(?P<category>COMMISSIONS)(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>(?P<category>REMUNERATION).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<category>REMISE CHEQUES)(?P<text>.*)'), FrenchTransaction.TYPE_DEPOSIT),
    ]


class ActionNeededPage(LoggedPage, HTMLPage):
    def has_skippable_action_needed(self):
        # NB: The CGUs happens on every page as long as it is not skipped or
        # validated. The implementation is done in the Accounts page because
        # we decide to skip the CGUs in browser.iter_accounts()
        return bool(self.doc.xpath('//input[@class="bouton_valid01" and contains(@title, "Me le demander ultérieurement")]'))

    def get_action_needed_message(self):
        warning = CleanText(
            '//div[@id="message_renouvellement_mot_passe"]'
            '| //span[contains(text(), "Votre identifiant change")]'
            '| //span[contains(text(), "Nouveau mot de passe")]'
            '| //span[contains(text(), "Renouvellement de votre mot de passe")]'
            '| //span[contains(text(), "Mieux vous connaître")]'
            '| //span[contains(text(), "Souscrivez au Livret + en quelques clics")]'
            '| //p[@class="warning" and contains(text(), "Cette opération sensible doit être validée par un code sécurité envoyé par SMS")]'
        )(self.doc)
        if warning:
            return warning

    def get_global_error_message(self):
        return CleanText(
            '//div[@id="as_renouvellementMIFID.do_"]/div[contains(text(), "Bonjour")]'
            '| //div[contains(@id, "Bloquant")]//div[@class="content_message"]'
            '| //p[contains(text(), "Et si vous faisiez de Fortuneo votre banque principale")]'
            '| //div[@id="as_renouvellementMotDePasse.do_"]//p[contains(text(), "votre mot de passe")]'
            '| //div[@id="as_afficherSecuriteForteOTPIdentification.do_"]//span[contains(text(), "Pour valider ")]'
        )(self.doc)

    def get_local_error_message(self):
        return CleanText('//div[@id="error"]/p[@class="erreur_texte1"]')(self.doc)


MARKET_ORDER_DIRECTIONS = {
    'Achat': MarketOrderDirection.BUY,
    'Vente': MarketOrderDirection.SALE,
}

MARKET_ORDER_TYPES = {
    'MAR': MarketOrderType.MARKET,
    'DC': MarketOrderType.MARKET,
    'LIM': MarketOrderType.LIMIT,
    'AML': MarketOrderType.LIMIT,
    'ASD': MarketOrderType.TRIGGER,
    'APD': MarketOrderType.TRIGGER,
}


class PeaHistoryPage(ActionNeededPage):
    def on_load(self):
        err_msgs = [
            "vos informations personnelles n'ayant pas été modifiées récemment, nous vous remercions de bien vouloir les compléter",
            "nous vous remercions de mettre à jour et/ou de compléter vos informations personnelles",
        ]
        text = CleanText('//div[@class="block_cadre"]//div/p')(self.doc)
        if any(err_msg in text for err_msg in err_msgs):
            raise ActionNeeded(text)

    @method
    class iter_investments(TableElement):
        item_xpath = '//table[@id="t_intraday"]/tbody/tr[not(has-class("categorie") or has-class("detail") or has-class("detail02"))]'
        head_xpath = '//table[@id="t_intraday"]/thead//th'

        col_label = 'Libellé'
        col_unitvalue = 'Cours'
        col_quantity = 'Qté'
        col_unitprice = 'PRU / PM'
        col_valuation = 'Valorisation'
        col_diff = '+/- values'
        col_portfolio_share = 'Poids'

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return Field('valuation')(self)

            obj_label = CleanText(TableCell('label'))
            obj_id = Base(TableCell('label'), Regexp(Link('./a[contains(@href, "cdReferentiel")]'), r'cdReferentiel=(.*)'))
            obj_code = IsinCode(Regexp(Field('id'), r'^[A-Z]+[0-9]+(.*)$'), default=NotAvailable)
            obj_code_type = IsinType(Regexp(Field('id'), r'^[A-Z]+[0-9]+(.*)$'), default=NotAvailable)
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(TableCell('unitvalue'), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell('valuation'), default=NotAvailable)

            obj_diff = Base(TableCell('diff'), CleanDecimal.French('./text()', default=NotAvailable))

            def obj_diff_ratio(self):
                diff_ratio_percent = Base(TableCell('diff'), CleanDecimal.French('./span', default=None))(self)
                if diff_ratio_percent:
                    return diff_ratio_percent / 100
                return NotAvailable

    def get_liquidity(self):
        return CleanDecimal.French('//*[@id="valorisation_compte"]/table/tr[3]/td[2]', default=0)(self.doc)

    def select_period(self):
        try:
            form = self.get_form(name='form_historique_titres')
        except FormNotFound:
            return False
        form['dateDebut'] = (date.today() - relativedelta(years=2)).strftime('%d/%m/%Y')
        form['nbResultats'] = '100'
        form['typeOperation'] = '01'
        form.submit()
        return True

    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="tabHistoriqueOperations"]/tbody/tr'
        head_xpath = '//table[@id="tabHistoriqueOperations"]/thead//th'

        col_raw = 'Opération'
        col_date = 'Date'
        col_amount = 'Montant brut'
        col_commission = re.compile(r'Courtage')
        col_currency = 'Devise'

        col_inv_label = 'Libellé'
        col_inv_quantity = 'Qté'
        col_inv_unitvalue = "Prix d'éxé"

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return CleanText(TableCell('currency'))(self)

            obj_type = Transaction.TYPE_BANK

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_label = obj_raw = CleanText(TableCell('raw'))
            obj_amount = CleanDecimal.French(TableCell('amount'), default=0)
            obj_commission = CleanDecimal.French(TableCell('commission'))

            def obj_investments(self):
                investment = Investment()
                investment.valuation = Field('amount')(self)
                investment.label = CleanText(TableCell('inv_label'))(self)
                investment.quantity = CleanDecimal.French(TableCell('inv_quantity'), default=0)(self)
                investment.unitvalue = CleanDecimal.French(TableCell('inv_unitvalue'), default=0)(self)
                return [investment]

            obj__details_link = None

    @method
    class fill_account(ItemElement):
        def obj_balance(self):
            valuations = self.xpath('//div[@id="valorisation_compte"]//table/tr')

            # If this is a market account, we must remove the liquidities from the account balance.
            # They are already fetched as another account.
            if 'mes-comptes/compte-titres-pea' in self.page.url:
                for valuation in valuations:
                    if 'Évaluation Titres' in CleanText('.')(valuation):
                        return CleanDecimal.French('./td[2]')(valuation)
            for valuation in valuations:
                if 'Valorisation totale' in CleanText('.')(valuation):
                    return CleanDecimal.French('./td[2]')(valuation)

        def obj_currency(self):
            return Currency('//div[@id="valorisation_compte"]//td[contains(text(), "Solde")]')(self)

        def obj__market_orders_link(self):
            return AbsoluteLink('//a[contains(@href, "carnet-d-ordres.jsp")]')(self)

    def get_date_range_form(self):
        today = date.today()
        form = self.get_form()
        form['dateDeb'] = (today - relativedelta(years=1)).strftime('%d/%m/%Y')
        form['dateFin'] = today.strftime('%d/%m/%Y')
        return form

    def are_market_orders_loaded(self):
        return bool(self.doc.xpath('//form[@id="afficherCarnetOrdre"]'))

    def get_parameters_hash(self):
        return Attr('//input[@value="as_afficherCarnetOrdre.do_"]', 'name')(self.doc)

    @method
    class iter_market_orders(TableElement):
        item_xpath = '//table[@id="t_intraday"]/tbody/tr[td and not(./td[contains(text(), "Aucun ordre")])]'
        head_xpath = '//table[@id="t_intraday"]/thead//th'

        col_label = re.compile(r'.*Libellé')
        col_direction = 'Sens'
        col_quantity = 'Qté'
        col_order_type_ordervalue = re.compile(r'Type')
        col_validity_date = 'Validité'
        col_state_unitprice = 'Etat'
        col_date = 'Transmission'
        col_currency = 'Devise'

        class item(ItemElement):
            klass = MarketOrder

            obj__details_link = AbsoluteLink('.//a[@class="bt_l_loupe"]', default=NotAvailable)
            obj_id = Regexp(
                Link('.//a[@class="bt_l_loupe"]', default=NotAvailable),
                r'idOrdre=([^&]+)',
                default=NotAvailable,
            )
            obj_label = CleanText(TableCell('label'))
            obj_direction = MapIn(CleanText(TableCell('direction')), MARKET_ORDER_DIRECTIONS, MarketOrderDirection.UNKNOWN)
            obj_quantity = CleanDecimal.French(TableCell('quantity'))
            obj_order_type = MapIn(CleanText(TableCell('order_type_ordervalue')), MARKET_ORDER_TYPES, MarketOrderType.UNKNOWN)
            obj_ordervalue = CleanDecimal.French(
                Regexp(CleanText(TableCell('order_type_ordervalue')), r'\(.*\)', default=NotAvailable),
                default=NotAvailable,
            )
            obj_validity_date = Date(CleanText(TableCell('validity_date')), dayfirst=True)

            # If the order has been executed, the state is followed by the unit price.
            obj_state = Regexp(CleanText(TableCell('state_unitprice')), r'(.+?)\d|$', default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('state_unitprice'), default=NotAvailable)

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_currency = Currency(TableCell('currency'))

    @method
    class fill_market_order(ItemElement):
        obj_execution_date = Date(
            Regexp(CleanText('//tr[contains(./th, "Date et heure d\'exécution")]/td'), r'(.*) -', default=NotAvailable),
            dayfirst=True,
            default=NotAvailable,
        )
        obj_unitvalue = CleanDecimal.French('//tr/th[contains(text(), "Dernier")]/following-sibling::td[1]')
        obj_code = IsinCode(CleanText('//tr[contains(./th, "Code ISIN")]/td'), default=NotAvailable)
        obj_stock_market = CleanText('//tr[contains(./th, "Place de cotation")]/td')


class InvestmentHistoryPage(ActionNeededPage):
    @method
    class iter_investments(TableElement):
        item_xpath = '//table[@id="tableau_support"]/tbody/tr'
        head_xpath = '//table[@id="tableau_support"]/thead//th'

        col_label = 'Libellé'
        col_quantity = 'Nombre de parts'
        col_unitvalue = 'Valeur Liquidative'
        col_vdate = 'Date de valeur'
        col_valuation = 'Montant'
        col_portfolio_share = 'Poids'
        col_unitprice = 'Prix de revient'
        col_diff_ratio = 'Performance'
        col_diff = re.compile(r'\+/- value financière')

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_id = Base(TableCell('label'), Regexp(Link('./a[contains(@href, "cdReferentiel")]'), r'cdReferentiel=(.*)'))
            obj_code = IsinCode(Regexp(Field('id'), r'^[A-Z]+[0-9]+(.*)$'), default=NotAvailable)
            obj_code_type = IsinType(Regexp(Field('id'), r'^[A-Z]+[0-9]+(.*)$'), default=NotAvailable)
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(TableCell('unitvalue'), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell('valuation'))
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True, default=NotAvailable)
            obj_diff = CleanDecimal.French(TableCell('diff'), default=NotAvailable)

            def obj_diff_ratio(self):
                diff_ratio_percent = CleanDecimal.French(TableCell('diff_ratio'), default=None)(self)
                if diff_ratio_percent:
                    return diff_ratio_percent / 100
                return NotAvailable

    def select_period(self):
        assert isinstance(self.browser.page, type(self))

        try:
            form = self.get_form(name='OperationsForm')
        except FormNotFound:
            return False

        form['dateDebut'] = (date.today() - relativedelta(years=2)).strftime('%d/%m/%Y')
        form['nbrEltsParPage'] = '100'
        form.submit()
        return True

    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="tableau_histo_opes" and not(thead/tr/th[contains(text(), "ISIN")])]/tbody/tr'
        head_xpath = '//table[@id="tableau_histo_opes" and not(thead/tr/th[contains(text(), "ISIN")])]/thead//th'

        col_details_link = 'Détail'
        col_date = "Date d'opération"
        col_raw = 'Libellé'
        col_amount = re.compile(r'Montant Net')

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return CleanDecimal.French(TableCell('amount'), default=None)(self) is not None

            obj_type = Transaction.TYPE_BANK

            obj_date = obj_rdate = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_label = obj_raw = CleanText(TableCell('raw'))
            obj_amount = CleanDecimal.French(TableCell('amount'), default=0)

            obj__details_link = Base(TableCell('details_link'), Regexp(Attr('./a', 'onclick', default=''), r"afficherDetailOperation\('([^']+)", default=''))

    @method
    class iter_detail_history(TableElement):
        item_xpath = '//form[@name="DetailOperationForm"]//table[not(thead/tr/th[contains(text(), "ISIN")])]/tbody/tr[not(@id)][td[3]]'
        head_xpath = '//form[@name="DetailOperationForm"]//table[not(thead/tr/th[contains(text(), "ISIN")])]/thead//th'

        col_date = 'Date'
        col_raw = 'Libellé'
        col_amount = 'Montant'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return CleanDecimal.French(TableCell('amount'), default=None)(self) is not None

            obj_type = Transaction.TYPE_BANK

            obj_date = obj_rdate = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_label = obj_raw = CleanText(TableCell('raw'))
            obj_amount = CleanDecimal.French(TableCell('amount'), default=0)

            obj__details_link = None

    @method
    class fill_account(ItemElement):
        def obj_balance(self):
            for div in self.xpath('//div[@class="block synthese_vie"]/div/div/div'):
                if 'Valorisation' in CleanText('.')(div):
                    return CleanDecimal.French('./p[@class="synthese_data_line_right_text"]')(div)

        def obj_currency(self):
            for div in self.xpath('//div[@class="block synthese_vie"]/div/div/div'):
                if 'Valorisation' in CleanText('.')(div):
                    return Currency('./p[@class="synthese_data_line_right_text"]')(div)


class AccountHistoryPage(ActionNeededPage):
    def build_doc(self, content):
        content = re.sub(br'\*<E\w+', b'*', content)
        return super(AccountHistoryPage, self).build_doc(content)

    @method
    class fill_account(ItemElement):
        def obj_coming(self):
            for tr in self.xpath('//table[@id="tableauConsultationHisto"]/tbody/tr'):
                if 'Encours' in CleanText('./td')(tr):
                    return CleanDecimal('./td//strong', replace_dots=True, sign=lambda x: -1, default=NotAvailable)(tr)

        def obj_balance(self):
            for tr in self.xpath('//table[@id="tableauConsultationHisto"]/tbody/tr'):
                if 'Solde' in CleanText('./td')(tr):
                    return CleanDecimal.French('./td/strong')(tr)

        def obj_currency(self):
            for tr in self.xpath('//table[@id="tableauConsultationHisto"]/tbody/tr'):
                if 'Solde' in CleanText('./td')(tr):
                    return Currency('./td/strong')(tr)

    def iter_investments(self):
        return []

    def select_period(self):
        try:
            form = self.get_form(xpath='//form[@name="ConsultationHistoriqueOperationsForm" '
                                       ' or @name="form_historique_titres" '
                                       ' or @name="OperationsForm"]')
        except FormNotFound:
            return False

        form['dateRechercheDebut'] = (date.today() - relativedelta(years=2)).strftime('%d/%m/%Y')
        form['nbrEltsParPage'] = '100'
        form.submit()

        return True

    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="tabHistoriqueOperations"]/tbody/tr'
        head_xpath = '(//table[@id="tabHistoriqueOperations"]/thead)[1]//th'

        col_date = "Date d'opération"
        col_vdate = 'Date de valeur'
        col_label = 'Libellé'
        col_debit = 'Débit'
        col_credit = 'Crédit'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return Field('amount')(self) != 0

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True, default=NotAvailable)
            obj_raw = Transaction.Raw(Base(TableCell('label'), CleanText('./text()')))

            def obj_label(self):
                return (
                    Base(TableCell('label'), CleanText('./div'))(self)
                    or Base(TableCell('label'), CleanText('./text()'))(self)
                )

            def obj_amount(self):
                return (
                    CleanDecimal.US(TableCell('credit'), default=0)(self)
                    + CleanDecimal.US(TableCell('debit'), default=0)(self)
                )

            obj__details_link = None


class CardHistoryPage(ActionNeededPage):
    def iter_investments(self):
        return []

    def select_period(self):
        return True

    @method
    class iter_coming(TableElement):
        item_xpath = '//table[@id="tableauEncours"]/tbody/tr'
        head_xpath = '//table[@id="tableauEncours"]/thead//th'

        col_rdate = "Date d'opération"
        col_date = 'Date de prélèvement'
        col_raw = 'Libellé'
        col_debit = 'Débit'
        col_credit = 'Crédit'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return Field('amount')(self) != 0

            obj_raw = obj_label = CleanText(TableCell('raw'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_rdate = obj_bdate = Date(CleanText(TableCell('rdate')), dayfirst=True)
            obj_type = Transaction.TYPE_DEFERRED_CARD

            def obj_amount(self):
                return (
                    CleanDecimal.French(TableCell('credit'), default=0)(self)
                    + CleanDecimal.French(TableCell('debit'), default=0)(self)
                )

    def is_loading(self):
        return bool(self.doc.xpath('//span[@class="loading"]'))


ACCOUNT_TYPES = {
    'mes-comptes/compte-courant/consulter-situation': Account.TYPE_CHECKING,
    'mes-comptes/compte-especes': Account.TYPE_CHECKING,
    'mes-comptes/compte-courant/carte-bancaire': Account.TYPE_CARD,
    'mes-comptes/assurance-vie': Account.TYPE_LIFE_INSURANCE,
    'mes-comptes/livret': Account.TYPE_SAVINGS,
    'mes-comptes/pea': Account.TYPE_PEA,
    'mes-comptes/ppe': Account.TYPE_PEA,
    'mes-comptes/compte-titres-pea': Account.TYPE_MARKET,
    'mes-comptes/credit-immo': Account.TYPE_LOAN,
}


class AccountsList(ActionNeededPage):
    @method
    class fill_person_name(ItemElement):
        klass = Account

        # Contains the title (M., Mme., etc) + last name.
        # The first name isn't available in the person's details.
        obj_name = CleanText('//span[has-class("mon_espace_nom")]')

    def get_iframe_url(self):
        iframe = self.doc.xpath('//iframe[@id="iframe_centrale"]')
        if iframe:
            return iframe[0].attrib['src']

    def need_reload(self):
        form = self.doc.xpath('//form[@name="InformationsPersonnellesForm"]')
        return len(form) > 0

    def need_sms(self):
        return len(self.doc.xpath('//div[@id="aidesecuforte"]'))

    def has_accounts(self):
        accounts = self.doc.xpath('//div[contains(@class, " compte") and not(contains(@class, "compte_selected")) and not(contains(@class, "aut"))]')
        return len(accounts) > 0

    @method
    class iter_accounts(ListElement):
        item_xpath = '//div[contains(@class, " compte") and not(contains(@class, "compte_selected")) and not(contains(@class, "aut"))]'
        accounts = []

        class item(ItemElement):
            klass = Account

            obj__history_link = AbsoluteLink(
                './ul/li/a[contains(@id, "consulter_solde") '
                'or contains(@id, "historique") '
                'or contains(@id, "contrat") '
                'or contains(@id, "assurance_vie_operations")]',
                default=None
            )

            obj__investment_link = AbsoluteLink('./ul/li/a[contains(@id, "portefeuille")]', default=None)

            obj_id = obj_number = CleanText('./a[contains(@class, "numero_compte")]/div', replace=[('N° ', '')])
            obj__ca = CleanText('./a[contains(@class, "numero_compte")]/@rel')

            def obj__card_links(self):
                card_links = []
                card_link = AbsoluteLink('./ul/li/a[contains(text(), "Carte bancaire")]', default=None)(self)
                if card_link:
                    card_links.append(card_link)
                return card_links

            obj_label = CleanText('./a[contains(@class, "numero_compte")]/@title')
            obj_type = MapIn(Field('_history_link'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)

            def obj_ownership(self):
                regexp = re.search(r'(m\. |mme\. )(.+)', CleanText('//span[has-class("mon_espace_nom")]')(self), re.IGNORECASE)
                if regexp and len(regexp.groups()) == 2:
                    gender = regexp.group(1).replace('.', '').rstrip()
                    name = regexp.group(2)
                    label = Field('label')(self)
                    if re.search(r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)', label, re.IGNORECASE):
                        return AccountOwnership.CO_OWNER
                    if re.search(r'{} {}'.format(gender, name), label, re.IGNORECASE):
                        return AccountOwnership.OWNER
                    return AccountOwnership.ATTORNEY
                return NotAvailable


class FalseActionPage(ActionNeededPage):
    pass


class LoanPage(ActionNeededPage):
    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.French('//p[@id="c_montantRestant"]//strong')
        obj_total_amount = CleanDecimal.French('(//p[@id="c_montantEmprunte"]//strong)[2]')
        obj_next_payment_amount = CleanDecimal.French(Regexp(CleanText('//p[@id="c_prochaineEcheance"]//strong'), r'(.*) le'))
        obj_next_payment_date = Date(CleanText('//p[@id="c_prochaineEcheance"]//strong/strong'), dayfirst=True)
        obj_account_label = CleanText('//p[@id="c_comptePrelevementl"]//strong')
        obj_subscription_date = Date(CleanText('//p[@id="c_dateDebut"]//strong'), dayfirst=True)
        obj_maturity_date = Date(CleanText('//p[@id="c_dateFin"]//strong'), dayfirst=True)

        def obj_ownership(self):
            if bool(CleanText('//p[@id="c_emprunteurSecondaire"]')(self)):
                return AccountOwnership.CO_OWNER
            return AccountOwnership.OWNER


class ProfilePage(ActionNeededPage):
    def get_csv_link(self):
        return Link('//div[@id="bloc_telecharger"]//a[@id="telecharger_donnees"]', default=NotAvailable)(self.doc)

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_phone = Regexp(CleanText('//div[@id="consultationform_telephones"]/p[@id="c_numeroPortable"]'), r'([\d\*]+)', default=None)
        obj_email = CleanText('//div[@id="modification_email"]//p[@id="c_email_actuel"]/span')
        obj_address = CleanText('//div[@id="consultationform_adresse_domicile"]/div[@class="container"]//span')
        obj_job = CleanText('//div[@id="consultationform_informations_complementaires"]/p[@id="c_profession"]/span')
        obj_job_activity_area = CleanText('//div[@id="consultationform_informations_complementaires"]/p[@id="c_secteurActivite"]/span')
        obj_company_name = CleanText('//div[@id="consultationform_informations_complementaires"]/p[@id="c_employeur"]/span')


class ProfilePageCSV(LoggedPage, CsvPage):
    ENCODING = 'latin_1'
    if sys.version_info.major > 2:
        FMTPARAMS = {'delimiter': ';'}
    else:
        FMTPARAMS = {'delimiter': b';'}

    def get_profile(self):
        d = {el[0]: el[1] for el in self.doc}
        profile = Person()
        profile.name = '%s %s' % (d['Nom'], d['Prénom'])
        profile.birth_date = parse_french_date(d['Date de naissance']).date()
        profile.address = '%s %s %s' % (d['Adresse de correspondance'], d['Code postal résidence fiscale'], d['Ville adresse de correspondance'])
        profile.country = d['Pays adresse de correspondance']
        profile.email = d['Adresse e-mail']
        profile.phone = d.get('Téléphone portable')
        profile.job_activity_area = d.get('Secteur d\'activité')
        profile.job = d.get('Situation professionnelle')
        profile.company_name = d.get('Employeur')
        profile.family_situation = d.get('Situation familiale')
        return profile


class SecurityPage(ActionNeededPage):
    pass


class InformationsPage(ActionNeededPage):
    pass
