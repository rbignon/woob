# Copyright(C) 2010-2011  Nicolas Duhamel
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

import re
from decimal import Decimal
from urllib.parse import urljoin

from woob.browser.elements import ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import AbsoluteLink, Link, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    Async, CleanDecimal, CleanText, Coalesce, Currency, Date, Env, Field, Format, Lower, MapIn, Regexp, Upper,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, PartialHTMLPage, RawPage
from woob.capabilities.bank import Account, AccountOwnerType, Loan
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.contact import Advisor
from woob.capabilities.profile import Person
from woob.exceptions import BrowserUnavailable
from woob.tools.pdf import extract_text

from .base import MyHTMLPage


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


def MyDate(*args, **kwargs):
    kwargs.update(dayfirst=True, default=NotAvailable)
    return Date(*args, **kwargs)


ACCOUNTS_TYPES = {
    'comptes? bancaires?': Account.TYPE_CHECKING,
    'ccp': Account.TYPE_CHECKING,
    'compte courant postal': Account.TYPE_CHECKING,
    "plan d'epargne populaire": Account.TYPE_SAVINGS,
    'livrets?': Account.TYPE_SAVINGS,
    'epargnes? logement': Account.TYPE_SAVINGS,
    "autres produits d'epargne": Account.TYPE_SAVINGS,
    'compte relais': Account.TYPE_SAVINGS,
    'comptes? titres? et pea': Account.TYPE_MARKET,
    'compte-titres': Account.TYPE_MARKET,
    'assurances? vie': Account.TYPE_LIFE_INSURANCE,
    'pret immobilier': Account.TYPE_MORTGAGE,
    'pret': Account.TYPE_LOAN,
    'renouvelable': Account.TYPE_REVOLVING_CREDIT,
    'credits?': Account.TYPE_LOAN,
    "plan d'epargne en actions": Account.TYPE_PEA,
    'comptes? attente': Account.TYPE_CHECKING,
    'perp': Account.TYPE_PERP,
    'assurances? retraite': Account.TYPE_PERP,
    'cachemire': Account.TYPE_LIFE_INSURANCE,
    'tonifia': Account.TYPE_LIFE_INSURANCE,
    'vivaccio': Account.TYPE_LIFE_INSURANCE,
    'gmo': Account.TYPE_LIFE_INSURANCE,
    'solesio vie': Account.TYPE_LIFE_INSURANCE,
}


class item_account_generic(ItemElement):
    klass = Account

    def condition(self):
        # For some loans the following xpath is absent and we don't want to skip them
        # Also a case of loan that is empty and has no information exists and will be ignored
        return (
            Coalesce(
                CleanDecimal.French('.//span[@class="number"]', default=None),
                CleanDecimal.French('.//*[@class="amount-euro"]', default=None),
                default=None,
            )(self.el)
            or (
                Field('type')(self) in (Account.TYPE_LOAN, Account.TYPE_MORTGAGE)
                and not any((
                    self.el.xpath('.//div//*[contains(text(),"pas la restitution de ces données.")]'),
                    self.el.xpath('.//div[contains(@class, "amount")]//span[contains(text(), "Contrat résilié")]'),
                    self.el.xpath('.//div[contains(@class, "amount")]//span[contains(text(), "Remboursé intégralement")]'),
                    self.el.xpath('.//div[contains(@class, "amount")]//span[contains(text(), "Prêt non débloqué")]'),
                ))
            )
        )

    obj_id = obj_number = Regexp(CleanText('./div/h3/a/span[contains(text(), "N°")]'), r'N° (\w+)')
    obj_currency = Coalesce(
        Currency('.//*[@class="amount-euro"]'),
        Currency('.//span[@class="number"]'),
        Currency('.//span[@class="thick"]'),
        Currency('.//span[@class="amount"]'),
    )
    obj_owner_type = AccountOwnerType.PRIVATE
    obj__account_holder = Lower('./div/h3/a/span[2]')

    def obj_url(self):
        if Field('type')(self) in (Account.TYPE_LOAN, Account.TYPE_REVOLVING_CREDIT, Account.TYPE_MORTGAGE):
            return AbsoluteLink('./div/h3/a')(self)
        return Link('./div/h3/a')(self)

    obj_label = CleanText('.//h3/a/span[@class="pseudo-h3"]')

    def obj_balance(self):
        if Field('type')(self) in (Account.TYPE_LOAN, Account.TYPE_MORTGAGE):
            balance = CleanDecimal.French('.//p[@class="amount-euro"]', default=NotAvailable)(self)
            if empty(balance):
                balance = CleanDecimal.French('.//span[@class="number"]', default=NotAvailable)(self)
            if balance:
                balance = -abs(balance)
            return balance
        balance = CleanDecimal.French('.//p[@class="amount-euro"]', default=NotAvailable)(self)
        if empty(balance):
            balance = CleanDecimal.French('.//span[@class="number"]')(self)
        return balance

    def obj_coming(self):
        if Field('type')(self) == Account.TYPE_CHECKING and Field('balance')(self) != 0:
            # When the balance is 0, we get a website unavailable on the history page
            # and the following navigation is broken
            has_coming = False
            coming = 0

            details_page = self.page.browser.open(Field('url')(self))
            if not details_page.page:
                # Details page might not always be available
                return NotAvailable

            # the tag looks like "Opérations <br/> à venir" so we need to use both text nodes
            coming_op_link = Coalesce(
                Link(
                    '//a[contains(text(), "Opérations") and contains(text()[2], "à venir")]',
                    default=None
                ),
                Link('//a[contains(text(), "Opérations à venir")]', default=None),
                default=NotAvailable,
            )(details_page.page.doc)

            if coming_op_link:
                coming_op_link = Regexp(pattern=r'../(.*)').filter(coming_op_link)
                coming_operations = self.page.browser.open(
                    self.page.browser.BASEURL + '/voscomptes/canalXHTML/CCP/' + coming_op_link
                )
            else:
                coming_op_link = Coalesce(
                    Link(
                        '//a[contains(text(), "Opérations") and contains(text()[2], "en cours")]',
                        default=None,
                    ),
                    Link('//a[contains(text(), "Opérations en cours")]', default=None),
                )(details_page.page.doc)
                coming_operations = self.page.browser.open(coming_op_link)

            if CleanText('//span[@id="amount_total"]')(coming_operations.page.doc):
                has_coming = True
                coming += CleanDecimal('//span[@id="amount_total"]', replace_dots=True)(coming_operations.page.doc)

            if CleanText('.//dt[contains(., "Débit différé à débiter")]')(self):
                has_coming = True
                coming += CleanDecimal(
                    './/dt[contains(., "Débit différé à débiter")]/following-sibling::dd[1]',
                    replace_dots=True
                )(self)

            if has_coming:
                return coming

        return NotAvailable

    def obj_iban(self):
        if not Field('url')(self):
            return NotAvailable
        if Field('type')(self) not in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            return NotAvailable

        details_page = self.page.browser.open(Field('url')(self)).page
        if not details_page:
            # Details page might not always be available
            return NotAvailable

        rib_link = Link('//a[.//abbr[contains(text(), "RIB")]]', default=NotAvailable)(details_page.doc)
        if rib_link:
            response = self.page.browser.open(rib_link)
            return response.page.get_iban()

        elif Field('type')(self) == Account.TYPE_SAVINGS:
            # The rib link is available on the history page (ex: Livret A)
            his_page = self.page.browser.open(Field('url')(self))
            rib_link = Link('//a[.//abbr[contains(text(), "RIB")]]', default=NotAvailable)(his_page.page.doc)
            if rib_link:
                response = self.page.browser.open(rib_link)
                return response.page.get_iban()
        return NotAvailable

    def obj_type(self):
        # first trying to match with label
        label = Lower(Field('label'), transliterate=True)(self)
        # then by type (not on the loans page)
        type_ = Regexp(
            Lower(
                './ancestor::ul/preceding-sibling::div[@class="assets" or @class="avoirs"][1]//h2[1]',
                transliterate=True,
            ),
            r'(\d+) (.*)',
            '\\2',
            default=None,
        )(self)
        # Finally match with the element's title
        for data in (label, type_):
            if data:
                for acc_type_key, acc_type in ACCOUNTS_TYPES.items():
                    if re.findall(acc_type_key, data):  # match with/without plural in type
                        return acc_type
        return Account.TYPE_UNKNOWN

    obj__has_cards = Link('../ul//a[contains(@href, "consultationCarte")]', default=None)
    obj__has_deferred_history = Link(
        './/div[contains(@class, "additional-data")]//a[contains(@href, init-mouvementsCarteDD)]',
        default=False
    )

    def obj__has_transfer(self):
        return bool(self.xpath(
            '//ul[@class="cartridge-links"]//a/span[contains(text(), "Virement")]'
        ))


class AccountList(LoggedPage, MyHTMLPage):
    def on_load(self):
        super().on_load()

        # website sometimes crash
        if CleanText('//h2[text()="ERREUR"]')(self.doc):
            self.browser.location('https://voscomptesenligne.labanquepostale.fr/voscomptes/canalXHTML/securite/authentification/initialiser-identif.ea')

            raise BrowserUnavailable()

    @property
    def no_accounts(self):
        return (
            len(
                self.doc.xpath("""
                    //iframe[contains(@src, "/comptes_contrats/sans_")]
                    | //iframe[contains(@src, "bel_particuliers/prets/prets_nonclient")]
                """)
            ) > 0
        )

    @property
    def has_mandate_management_space(self):
        return len(self.doc.xpath('//a[@title="Accéder aux Comptes Gérés Sous Mandat"]')) > 0

    def mandate_management_space_link(self):
        return Link('//a[@title="Accéder aux Comptes Gérés Sous Mandat"]')(self.doc)

    def get_error(self):
        return (
            CleanText('//div[contains(text(), "momentanément indisponible.")]')(self.doc)
            and not CleanText('//div[text()="Montant emprunté"]')(self.doc)
        )

    @method
    class iter_accounts(ListElement):
        @property
        def item_xpath(self):
            if self.xpath('//ul/li//div[contains(@class, "cartridge")]'):
                return '//ul/li//div[contains(@class, "cartridge")]'
            # Old version
            return '//ul/li//div[contains(@class, "account-resume")]'

        class item_account(item_account_generic):
            def condition(self):
                return item_account_generic.condition(self)

    def get_mandate_accounts_urls(self):
        return self.doc.xpath('//ul/li//a[contains(@class, "cartridge")]/@href')

    @method
    class get_personal_loan(ItemElement):
        klass = Loan

        def condition(self):
            loan_state = CleanText('//div[div[contains(text(), "Détail de votre")]]/div[4]')(self)
            return loan_state != 'Prêt soldé'

        obj_balance = CleanDecimal.French('//div[div[contains(text(), "Montant du capital restant")]]/div[4]', sign='-')
        obj_total_amount = CleanDecimal.French('//div[div[contains(text(), "Montant emprunté")]]/div[2]')
        obj_nb_payments_left = CleanDecimal(
            CleanText('//div[div[contains(text(), "restant à rembourser")]]/div[2]'),
            default=NotAvailable
        )
        obj_next_payment_date = Date(
            CleanText(
                '//div[div[contains(text(), "prochaine échéance")]]/div[2]'
            ),
            dayfirst=True,
            default=NotAvailable,
        )
        obj_rate = CleanDecimal.French(
            '//div[div[text()="TAEG fixe :"]]/div[2]',
            default=NotAvailable,
        )
        obj_type = Account.TYPE_LOAN
        obj_owner_type = AccountOwnerType.PRIVATE
        obj__account_holder = NotAvailable

        def obj_next_payment_amount(self):
            if Field('next_payment_date')(self):
                return CleanDecimal.French(
                    CleanText('//div[div[contains(text(), "Mensualité") or contains(text(), "Echéance :")]]/div[2]'),
                    default=NotAvailable
                )(self)
            else:
                return NotAvailable

        def obj_insurance_label(self):
            label = CleanText('//div[div[contains(text(), "Assurance")]]/div[2]', default='Sans assurance')(self)
            if label == 'Sans assurance':
                return NotAvailable
            return label

        def obj_insurance_amount(self):
            if Field('insurance_label')(self):
                return CleanDecimal.French('//div[div[contains(text(), "Dont assurance")]]/div[2]')(self)
            return NotAvailable

    @method
    class iter_loans(TableElement):
        head_xpath = '//table[@id="pret" or @class="dataNum"]/thead//th'
        item_xpath = '//table[@id="pret"]/tbody/tr'

        col_label = ('Numéro du prêt', "Numéro de l'offre")
        col_total_amount = 'Montant initial emprunté'
        col_subscription_date = 'MONTANT INITIAL EMPRUNTÉ'
        col_next_payment_amount = 'Montant prochaine échéance'
        col_next_payment_date = 'Date prochaine échéance'
        col_balance = re.compile('Capital')
        col_maturity_date = re.compile(u'Date dernière')

        class item_loans(ItemElement):
            # there is two cases : the mortgage and the consumption loan. These cases have differents way to get the details
            # except for student loans, you may have 1 or 2 tables to deal with

            # if 1 table, item_loans is used for student loan
            # if 2 tables, get_student_loan is used
            klass = Loan

            obj_owner_type = AccountOwnerType.PRIVATE

            def condition(self):
                if CleanText(TableCell('balance'))(self) != 'Prêt non débloqué':
                    return bool(not self.xpath('//caption[contains(text(), "Période de franchise du")]'))
                return CleanText(TableCell('balance'))(self) != 'Prêt non débloqué'

            def load_details(self):
                url = Link('.//a', default=NotAvailable)(self)
                return self.page.browser.async_open(url=url)

            obj_total_amount = CleanDecimal(TableCell('total_amount'), replace_dots=True, default=NotAvailable)

            def obj_id(self):
                if TableCell('label', default=None)(self):
                    return Regexp(CleanText(Field('label'), default=NotAvailable), r'- (\w{16})')(self)

                # student_loan
                if CleanText('//select[@id="numOffrePretSelection"]/option[@selected="selected"]')(self):
                    return Regexp(
                        CleanText(
                            '//select[@id="numOffrePretSelection"]/option[@selected="selected"]'
                        ),
                        r'(\d+)'
                    )(self)

                return CleanText(
                    '//form[contains(@action, "detaillerOffre") or contains(@action, "detaillerPretPartenaireListe-encoursPrets.ea")]/div[@class="bloc Tmargin"]/div[@class="formline"][2]/span/strong'
                )(self)

            def obj_type(self):
                label = Lower(Field('label'), transliterate=True)
                _type = MapIn(label, ACCOUNTS_TYPES, Account.TYPE_UNKNOWN)(self)
                if not _type:
                    self.logger.warning('Account %s untyped, please type it.', Field('label')(self))
                return _type

            obj_number = Field('id')

            def obj_label(self):
                cell = TableCell('label', default=None)(self)
                if cell:
                    return Upper(cell, default=NotAvailable)(self)

                return Upper(
                    '//form[contains(@action, "detaillerOffre") or contains(@action, "detaillerPretPartenaireListe-encoursPrets.ea")]/div[@class="bloc Tmargin"]/h2[@class="title-level2"]'
                )(self)

            def obj_balance(self):
                if CleanText(TableCell('balance'))(self) != u'Remboursé intégralement':
                    return -abs(CleanDecimal(TableCell('balance'), replace_dots=True)(self))
                return Decimal(0)

            def obj_subscription_date(self):
                xpath = '//form[contains(@action, "detaillerOffre")]/div[1]/div[2]/span'
                if 'souscrite le' in CleanText(xpath)(self):
                    return MyDate(
                        Regexp(
                            CleanText(xpath),
                            r' (\d{2}/\d{2}/\d{4})',
                            default=NotAvailable
                        )
                    )(self)

                return NotAvailable

            obj_next_payment_amount = CleanDecimal(
                TableCell('next_payment_amount'),
                replace_dots=True,
                default=NotAvailable
            )

            def obj_maturity_date(self):
                if Field('subscription_date')(self):
                    async_page = Async('details').loaded_page(self)
                    return MyDate(
                        CleanText('//div[@class="bloc Tmargin"]/dl[2]/dd[4]')
                    )(async_page.doc)

                return MyDate(CleanText(TableCell('maturity_date', default='')), default=NotAvailable)(self)

            def obj_last_payment_date(self):
                xpath = '//div[@class="bloc Tmargin"]/div[@class="formline"][2]/span'
                if 'dont le dernier' in CleanText(xpath)(self):
                    return MyDate(
                        Regexp(
                            CleanText(xpath),
                            r' (\d{2}/\d{2}/\d{4})',
                            default=NotAvailable
                        )
                    )(self)

                async_page = Async('details').loaded_page(self)
                return MyDate(
                    CleanText(
                        '//div[@class="bloc Tmargin"]/dl[1]/dd[2]'
                    ),
                    default=NotAvailable
                )(async_page.doc)

            obj_next_payment_date = MyDate(CleanText(TableCell('next_payment_date')), default=NotAvailable)

            def obj_url(self):
                url = Link('.//a', default=None)(self)
                if url:
                    return urljoin(self.page.url, url)
                return self.page.url

            obj__has_cards = False
            obj__account_holder = NotAvailable

    @method
    class get_student_loan(ItemElement):
        # 2 tables student loan
        klass = Loan

        def condition(self):
            return bool(self.xpath('//caption[contains(text(), "Période de franchise du")]'))

        # get all table headers
        def obj__heads(self):
            heads_xpath = '//table[@class="dataNum"]/thead//th'
            return [CleanText('.')(head) for head in self.xpath(heads_xpath)]

        # get all table elements
        def obj__items(self):
            items_xpath = '//table[@class="dataNum"]/tbody//td'
            return [CleanText('.')(item) for item in self.xpath(items_xpath)]

        def get_element(self, header_name):
            for index, head in enumerate(Field('_heads')(self)):
                if header_name in head:
                    return Field('_items')(self)[index]
            raise AssertionError()

        obj_id = Regexp(CleanText('//select[@id="numOffrePretSelection"]/option[@selected="selected"]'), r'(\d+)')
        obj_type = Account.TYPE_LOAN
        obj_owner_type = AccountOwnerType.PRIVATE
        obj__account_holder = NotAvailable
        obj__has_cards = False

        def obj_total_amount(self):
            return CleanDecimal(replace_dots=True).filter(self.get_element('Montant initial'))

        def obj_label(self):
            return Regexp(CleanText('//h2[@class="title-level2"]'), r'([\w ]+)', flags=re.U)(self)

        def obj_balance(self):
            return -CleanDecimal(replace_dots=True).filter(self.get_element('Capital restant'))

        def obj_maturity_date(self):
            return Date(dayfirst=True).filter(self.get_element('Date derni'))

        def obj_duration(self):
            return CleanDecimal().filter(self.get_element("de l'amortissement"))

        def obj_next_payment_date(self):
            return Date(dayfirst=True).filter(self.get_element('Date de prochaine'))

        def obj_next_payment_amount(self):
            if 'Donnée non disponible' in CleanText().filter(self.get_element('Montant prochaine')):
                return NotAvailable
            return CleanDecimal(replace_dots=True).filter(self.get_element('Montant prochaine'))

        def obj_url(self):
            return self.page.url


class Advisor(LoggedPage, MyHTMLPage):
    @method
    class get_advisor(ItemElement):
        klass = Advisor

        obj_name = Env('name')
        obj_phone = Env('phone')
        obj_mobile = Env('mobile', default=NotAvailable)
        obj_agency = Env('agency', default=NotAvailable)
        obj_email = NotAvailable

        def obj_address(self):
            return (
                CleanText('//div[h3[contains(text(), "Bureau")]]/div[not(@class)][position() > 1]')(self)
                or NotAvailable
            )

        def parse(self, el):
            # we have two kinds of page and sometimes we don't have any advisor
            agency_phone = (
                CleanText('//span/a[contains(@href, "rendezVous")]', replace=[(' ', '')], default=NotAvailable)(self)
                or CleanText('//div[has-class("lbp-numero")]/span', replace=[(' ', '')], default=NotAvailable)(self)
            )

            advisor_phone = Regexp(
                CleanText('//div[h3[contains(text(), "conseil")]]//span[2]', replace=[(' ', '')]),
                r'(\d+)',
                default=""
            )(self)
            if advisor_phone.startswith(("06", "07")):
                self.env['phone'] = agency_phone
                self.env['mobile'] = advisor_phone
            else:
                self.env['phone'] = advisor_phone or agency_phone

            agency = CleanText('//div[h3[contains(text(), "Bureau")]]/div[not(@class)][1]')(self) or NotAvailable
            name = (
                CleanText('//div[h3[contains(text(), "conseil")]]//span[1]', default=None)(self)
                or CleanText('//div[@class="lbp-font-accueil"]/div[2]/div[1]/span[1]', default=None)(self)
            )
            if name:
                self.env['name'] = name
                self.env['agency'] = agency
            else:
                self.env['name'] = agency


class AccountRIB(LoggedPage, RawPage):
    iban_regexp = r'[A-Z]{2}\d{12}[0-9A-Z]{11}\d{2}'

    def get_iban(self):
        content = extract_text(self.data)
        if not content:
            # This can happen if there's an error on the site while rendering the PDF (no RIB is shown)
            return NotAvailable

        m = re.search(self.iban_regexp, content)
        if m:
            return m.group(0)
        return None


class MarketHomePage(LoggedPage, HTMLPage):
    pass


class MarketLoginPage(LoggedPage, PartialHTMLPage):
    def on_load(self):
        self.get_form(id='autoSubmit').submit()


class MarketCheckPage(LoggedPage, HTMLPage):
    pass


class UserTransactionIDPage(LoggedPage, JsonPage):
    def get_transaction_id(self):
        return self.doc['transactionId']


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = Format(
            '%s %s',
            CleanText(Dict('identite/prenomUsuel')),
            CleanText(Dict('identite/nomUsuel')),
        )
        obj_email = CleanText(Dict('contacts/courriel/adresse'), default=NotAvailable)
        obj_job = CleanText(Dict('activiteProfessionnelle/libelleProfession'), default=NotAvailable)


class RevolvingPage(LoggedPage, HTMLPage):
    @method
    class fill_revolving(ItemElement):
        obj_total_amount = CleanDecimal.French(
            '//span[text()="Montant maximum autorisé"]/following-sibling::span/text()',
            default=NotAvailable
        )
        obj_available_amount = CleanDecimal.French(
            '//span[text()="Montant disponible"]/following-sibling::span/text()',
            default=NotAvailable
        )
        obj_next_payment_date = Date(
            CleanText('//span[text()="Date du prélèvement"]/following-sibling::span/text()'),
            dayfirst=True
        )
        obj_last_payment_amount = CleanDecimal.French(
            '//span[text()="Montant dernière mensualité prélevée"]/following-sibling::span/text()'
        )
        obj_used_amount = CleanDecimal.French('//span[text()="Montant utilisé"]/following-sibling::span/text()')

        def obj_balance(self):
            return -abs(Field('used_amount')(self))

        def obj_insurance_label(self):
            label = CleanText(
                '//span[contains(text(), "Assurance")]/following-sibling::span/text()',
                default='Aucune Assurance'
            )(self)
            if label == 'Aucune Assurance':
                return NotAvailable
            return label

        def obj_insurance_amount(self):
            # page can have the label insurance but not the amount
            if (empty(Field('insurance_label')(self))
                    or empty(CleanText(
                        '//span[contains(text(), "Dont assurance au titre")]',
                        default=None
                    )(self))):
                return NotAvailable
            amount = 0
            for elem in self.xpath('//span[contains(text(), "Dont assurance au titre")]'):
                amount += CleanDecimal.French('following-sibling::span/text()')(elem)
            return amount

        obj__account_holder = NotAvailable
