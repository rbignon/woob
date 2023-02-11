# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

from woob.browser.pages import HTMLPage, LoggedPage, AbstractPage
from woob.browser.elements import ItemElement, TableElement, method, ItemElementFromAbstractPage, DictElement
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Currency, MapIn, Lower, Coalesce,
)
from woob.browser.filters.json import Dict
from woob.browser.filters.html import Attr, TableCell
from woob.capabilities.bank import Account, AccountOwnership
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable
from woob.tools.capabilities.bank.transactions import FrenchTransaction


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


class MyHTMLPage(HTMLPage):
    def get_view_state(self):
        return self.doc.xpath('//input[@name="javax.faces.ViewState"]')[0].attrib['value']

    def is_password_expired(self):
        return len(self.doc.xpath('//div[@id="popup_client_modifier_code_confidentiel"]'))

    def parse_number(self, number):
        # For some client they randomly displayed 4,115.00 and 4 115,00.
        # Browser is waiting for for 4 115,00 so we format the number to match this.
        if '.' in number and len(number.split('.')[-1]) == 2:
            return number.replace(',', ' ').replace('.', ',')
        return number

    def js2args(self, s):
        args = {}
        # For example:
        # noDoubleClic(this);;return oamSubmitForm('idPanorama','idPanorama:tableaux-comptes-courant-titre:0:tableaux-comptes-courant-titre-cartes:0:_idJsp321',null,[['paramCodeProduit','9'],['paramNumContrat','12234'],['paramNumCompte','12345678901'],['paramNumComptePassage','1234567890123456']]);
        for sub in re.findall("\['([^']+)','([^']+)'\]", s):
            args[sub[0]] = sub[1]

        sub = re.search('oamSubmitForm.+?,\'([^:]+).([^\']+)', s)
        args['%s:_idcl' % sub.group(1)] = "%s:%s" % (sub.group(1), sub.group(2))
        args['%s_SUBMIT' % sub.group(1)] = 1
        args['_form_name'] = sub.group(1)  # for woob only

        return args


ACCOUNT_TYPES = {
    'compte courant': Account.TYPE_CHECKING,
    'compte cheque': Account.TYPE_CHECKING,
    'compte basique': Account.TYPE_CHECKING,
    'compte joint': Account.TYPE_CHECKING,
    'livret': Account.TYPE_SAVINGS,
    "livret d'epargne": Account.TYPE_SAVINGS,
    'compte a terme': Account.TYPE_SAVINGS,
    'compte titres': Account.TYPE_MARKET,
    'epargne en actions': Account.TYPE_PEA,
    "plan d'epargne en actions": Account.TYPE_PEA,
    'checking': Account.TYPE_CHECKING,
    'saving': Account.TYPE_SAVINGS,
    'stock': Account.TYPE_MARKET,  # 'compte titres' and 'plan d'epargne en actions' have both the same type with the type field
}


class AccountsPage(AbstractPage):
    PARENT = 'allianzbanque'
    PARENT_URL = 'accounts'
    BROWSER_ATTR = 'package.browser.AllianzbanqueBrowser'

    @method
    class iter_accounts(DictElement):
        class item(ItemElementFromAbstractPage):
            PARENT = 'allianzbanque'
            PARENT_URL = 'accounts'
            BROWSER_ATTR = 'package.browser.AllianzbanqueBrowser'
            ITER_ELEMENT = 'iter_accounts'

            obj_type = Coalesce(
                MapIn(Lower(Dict('type')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN),
                MapIn(Lower(Dict('label')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN),
                default=Account.TYPE_UNKNOWN,
            )

    @method
    class iter_comings(DictElement):
        class item(ItemElementFromAbstractPage):
            PARENT = 'allianzbanque'
            PARENT_URL = 'transactions_comings'
            BROWSER_ATTR = 'package.browser.AllianzbanqueBrowser'
            ITER_ELEMENT = 'iter_comings'

            obj_label = Coalesce(
                CleanText(Dict('label'), default=''),
                CleanText(Dict('family'), default=''),
            )



class BankTransaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^RET(RAIT) DAB (?P<dd>\d{2})/(?P<mm>\d{2}) (?P<text>.*)'), FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r'^(CARTE|CB ETRANGER|CB) (?P<dd>\d{2})/(?P<mm>\d{2}) (?P<text>.*)'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^(?P<category>VIR(EMEN)?T? (SEPA)?(RECU|FAVEUR)?)( /FRM)?(?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^PRLV (?P<text>.*)( \d+)?$'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(CHQ|CHEQUE) .*$'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(AGIOS /|FRAIS) (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(CONVENTION \d+ |F )?COTIS(ATION)? (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(F|R)-(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^REMISE (?P<text>.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)( \d+)? QUITTANCE .*'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^.* LE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})$'), FrenchTransaction.TYPE_UNKNOWN),
        (re.compile(r'^ACHATS (CARTE|CB)'), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r'^ANNUL (?P<text>.*)'), FrenchTransaction.TYPE_PAYBACK)
    ]


class TransactionsPage(LoggedPage, MyHTMLPage):
    COL_DATE = 0
    COL_TEXT = 1
    COL_DEBIT = 2
    COL_CREDIT = 3

    def check_error(self):
        error = CleanText(default="").filter(self.doc.xpath('//p[@class="question"]'))
        return error if u"a expiré" in error else None

    def get_loan_balance(self):
        # Loan balances are positive on the website so we change the sign
        return CleanDecimal.US('//*[@id="table-detail"]/tbody/tr/td[@class="capital"]', sign='-', default=NotAvailable)(self.doc)

    def get_loan_currency(self):
        return Currency('//*[@id="table-detail"]/tbody/tr/td[@class="capital"]', default=NotAvailable)(self.doc)

    def get_loan_ownership(self):
        co_owner = CleanText('//td[@class="coEmprunteur"]')(self.doc)
        if co_owner:
            return AccountOwnership.CO_OWNER
        return AccountOwnership.OWNER

    def open_market(self):
        # only for netfinca PEA
        self.browser.bourse.go()

    def go_action(self, action):
        names = {'investment': "Portefeuille", 'history': "Mouvements"}
        for li in self.doc.xpath('//div[@class="onglets"]/ul/li[not(script)]'):
            if not Attr('.', 'class', default=None)(li) and names[action] in CleanText('.')(li):
                url = Attr('./ancestor::form[1]', 'action')(li)
                args = self.js2args(Attr('./a', 'onclick')(li))
                args['javax.faces.ViewState'] = self.get_view_state()
                self.browser.location(url, data=args)
                break

    @method
    class iter_investment(TableElement):
        item_xpath = '//table[contains(@id, "titres") or contains(@id, "OPCVM")]/tbody/tr'
        head_xpath = '//table[contains(@id, "titres") or contains(@id, "OPCVM")]/thead/tr/th[not(caption)]'

        col_label = 'Intitulé'
        col_quantity = 'NB'
        col_unitprice = re.compile('Prix de revient')
        col_unitvalue = 'Dernier cours'
        col_diff = re.compile('\+/- Values latentes')
        col_valuation = re.compile('Montant')

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_quantity = CleanDecimal(TableCell('quantity'))
            obj_unitprice = CleanDecimal(TableCell('unitprice'))
            obj_unitvalue = CleanDecimal(TableCell('unitvalue'))
            obj_valuation = CleanDecimal(TableCell('valuation'))
            obj_diff = CleanDecimal(TableCell('diff'))

            def obj_code(self):
                onclick = Attr(None, 'onclick').filter((TableCell('label')(self)[0]).xpath('.//a'))
                m = re.search(',\s+\'([^\'_]+)', onclick)
                return NotAvailable if not m else m.group(1)

            def condition(self):
                return CleanText(TableCell('valuation'))(self)

    def more_history(self):
        link = None
        for a in self.doc.xpath('.//a'):
            if a.text is not None and a.text.strip() == 'Sur les 6 derniers mois':
                link = a
                break

        form = self.doc.xpath('//form')[-1]
        if not form.attrib['action']:
            return None

        if link is None:
            # this is a check account
            args = {
                'categorieMouvementSelectionnePagination': 'afficherTout',
                'nbLigneParPageSelectionneHautPagination': -1,
                'nbLigneParPageSelectionneBasPagination': -1,
                'nbLigneParPageSelectionneComponent': -1,
                'idDetail:btnRechercherParNbLigneParPage': '',
                'idDetail_SUBMIT': 1,
                'javax.faces.ViewState': self.get_view_state(),
            }
        else:
            # something like a PEA or so
            value = link.attrib['id']
            id = value.split(':')[0]
            args = {
                '%s:_idcl' % id: value,
                '%s:_link_hidden_' % id: '',
                '%s_SUBMIT' % id: 1,
                'javax.faces.ViewState': self.get_view_state(),
                'paramNumCompte': '',
            }

        self.browser.location(form.attrib['action'], data=args)
        return True

    def get_deferred_card_history(self):
        # get all transactions
        form = self.get_form(id="hiddenCB")
        form['periodeMouvementSelectionnePagination'] = 4
        form['nbLigneParPageSelectionneHautPagination'] = -1
        form['nbLigneParPageSelectionneBasPagination'] = -1
        form['periodeMouvementSelectionneComponent'] = 4
        form['categorieMouvementSelectionneComponent'] = ''
        form['nbLigneParPageSelectionneComponent'] = -1
        form['idDetail:btnRechercherParNbLigneParPage'] = ''
        form['idDetail:btnRechercherParPeriode'] = ''
        form['idDetail_SUBMIT'] = 1
        form['idDetail:_idcl'] = ''
        form['paramNumCompte'] = ''
        form['idDetail:_link_hidden_'] = ''
        form['javax.faces.ViewState'] = self.get_view_state()
        form.submit()

        return True

    def get_history(self):
        # DAT account can't have transaction
        if self.doc.xpath('//table[@id="table-dat"]'):
            return
        # These accounts have investments, no transactions
        if self.doc.xpath('//table[@id="InfosPortefeuille"]'):
            return
        tables = self.doc.xpath('//table[@id="table-detail-operation"]')
        if len(tables) == 0:
            tables = self.doc.xpath('//table[@id="table-detail"]')
        if len(tables) == 0:
            tables = self.doc.xpath('//table[has-class("table-detail")]')
        if len(tables) == 0:
            assert len(self.doc.xpath('//td[has-class("no-result")]')) > 0
            return

        for tr in tables[0].xpath('.//tr'):
            tds = tr.findall('td')
            if len(tds) < 4:
                continue

            t = BankTransaction()
            date = ''.join([txt.strip() for txt in tds[self.COL_DATE].itertext()])
            raw = ''.join([txt.strip() for txt in tds[self.COL_TEXT].itertext()])
            debit = self.parse_number(''.join([txt.strip() for txt in tds[self.COL_DEBIT].itertext()]))
            credit = self.parse_number(''.join([txt.strip() for txt in tds[self.COL_CREDIT].itertext()]))

            t.parse(date, re.sub(r'[ ]+', ' ', raw), vdate=date)
            t.set_amount(credit, debit)
            yield t
