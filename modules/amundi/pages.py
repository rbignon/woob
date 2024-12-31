# Copyright(C) 2016      James GALT

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
from datetime import datetime
from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce, Date, Env, Eval, Field, Format, Map, Regexp, Title,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage
from woob.capabilities.bank import Account, AccountOwnerType, NoAccountsException, Transaction
from woob.capabilities.bank.wealth import Investment, Pocket
from woob.capabilities.base import NotAvailable, empty
from woob.tools.capabilities.bank.investments import IsinCode, IsinType

from .es_virtkeyboard_page import ESAmundiVirtKeyboard


def percent_to_ratio(value):
    if empty(value):
        return NotAvailable
    return value / 100


class LoginPage(JsonPage):
    VK_CLASS = ESAmundiVirtKeyboard

    def get_mfa_id(self):
        return Dict('jti')(self.doc)

    def get_current_domain(self):
        return Dict('domain')(self.doc)

    def get_token(self):
        return Dict('token', default=None)(self.doc)

    def get_keyboard(self):
        """ESAmundi keyboard"""
        return {
            'id': Dict('id')(self.doc),
            'base64': Dict('image')(self.doc),
        }

    def create_vk_password(self, password, keyboard):
        """ESAmundi keyboard"""
        vk = self.VK_CLASS(self.browser, keyboard['base64'])
        password_positions = vk.get_string_code(password)
        return password_positions


class MFAStatusPage(RawPage):
    def build_doc(self, content):
        if content.decode():
            return JsonPage.build_doc(self, content)
        return {}

    def get_token(self):
        return Dict('token', default=None)(self.doc)

    def get_current_domain(self):
        return Dict('domain')(self.doc)


class ConfigPage(JsonPage):
    def get_captcha_key(self):
        """ESAmundi Captcha"""
        return Dict('recaptchaPublicKey')(self.doc)


class AuthenticateFailsPage(JsonPage):
    pass


ACCOUNT_TYPES = {
    'PEE': Account.TYPE_PEE,
    'PEG': Account.TYPE_PEE,
    'PEI': Account.TYPE_PEE,
    'HES': Account.TYPE_PEE,
    'PERCO': Account.TYPE_PERCO,
    'PERCOI': Account.TYPE_PERCO,
    'PER': Account.TYPE_PER,
    'RSP': Account.TYPE_RSP,
    'ART 83': Account.TYPE_ARTICLE_83,
}


class AccountItemElement(ItemElement):
    klass = Account

    obj_id = CleanText(Dict('codeDispositif'))
    obj_balance = CleanDecimal.SI(Dict('mtBrut'))
    obj_currency = 'EUR'
    obj_type = Map(Dict('typeDispositif'), ACCOUNT_TYPES, Account.TYPE_LIFE_INSURANCE)
    obj_owner_type = AccountOwnerType.PRIVATE
    obj__is_master = Dict('flagDispositifMaitre', default=None)
    obj__master_id = Dict('idDispositifMaitre', default=None)
    obj__id_dispositif = CleanText(Dict('idDispositif'))
    obj__code_dispositif_lie = Dict('codeDispositifLie', default=None)
    obj__linked_accounts = []

    def obj__sub_accounts(self):
        if Field('_is_master')(self):
            return []
        return None

    def obj_number(self):
        # just the id is a kind of company id so it can be unique on a backend but not unique on multiple backends
        return Format('%s_%s', Field('id'), Env('username'))(self)

    def obj_label(self):
        # In case of a Article 83, the label is not libelleDispositif but libelleContrat
        # But it is not always present, so we check it before returning it
        # If it is not present, we return the libelleDispositif
        if Field('type')(self) == Account.TYPE_ARTICLE_83:
            contract_label = Dict('libelleContrat', default=None)(self)
            if contract_label:
                return contract_label
        label = Dict('libelleDispositif')(self)
        for encoding in ('iso-8859-2', 'latin1'):
            try:
                label = label.encode(encoding).decode('utf8')
                break
            except UnicodeError:
                continue
        return label


class InvestDictElement(DictElement):
    def find_elements(self):
        for invests in Dict('listPositionsSalarieDispositifsDto')(self):
            if invests.get('codeDispositif') == Env('account_id')(self):
                return invests.get('positionsSalarieFondsDto')
        return {}


class InvestItemElement(ItemElement):
    klass = Investment

    def condition(self):
        # Some additional invests are present in the JSON but are not
        # displayed on the website, besides they have no valuation,
        # so we check the 'valuation' key before parsing them
        return Dict('mtBrut', default=None)(self)

    obj_label = Dict('libelleFonds')
    obj_unitvalue = CleanDecimal.SI((Dict('vl')))
    obj_vdate = Date(Dict('dtVl'))
    obj__details_url = Dict('urlFicheFonds', default=None)
    obj_code = IsinCode(Dict('codeIsin', default=NotAvailable), default=NotAvailable)
    obj_code_type = IsinType(Dict('codeIsin', default=NotAvailable))

    def obj_diff(self):
        diff = CleanDecimal.SI(Dict('mtPMV', default=None), default=NotAvailable)(self)
        # Some invests have no diff value but the website fills the json field with the valuation.
        if diff == Field('valuation')(self):
            return NotAvailable
        return diff

    def obj_portfolio_share(self):
        portfolio_share_percent = CleanDecimal.SI(Dict('pourcentageSupport', default=None), default=None)(self)
        if portfolio_share_percent is None:
            return NotAvailable
        return portfolio_share_percent / 100

    def obj_srri(self):
        srri = Dict('SRRI', default=None)(self)
        # When the srri is not available, the website can either display '0 - Non disponible' or not have a
        # 'SRRI' key at all
        if srri is None or srri.startswith('0'):
            return NotAvailable
        return int(srri)

    def obj_performance_history(self):
        # The Amundi JSON only contains 1 year and 5 years performances.
        # It seems that when a value is unavailable, they display '0.0' instead...
        perfs = {}
        if Dict('performanceDtoList/0/valeur', default=None)(self) not in (0.0, None):
            perfs[1] = Eval(
                lambda x: round(x / 100, 4),
                CleanDecimal.SI(Dict('performanceDtoList/0/valeur'))
            )(self)
        if Dict('performanceDtoList/1/valeur', default=None)(self) not in (0.0, None):
            perfs[5] = Eval(
                lambda x: round(x / 100, 4),
                CleanDecimal.SI(Dict('performanceDtoList/1/valeur'))
            )(self)
        return perfs

    # Fetch pockets for each investment:
    class obj__pockets(DictElement):
        item_xpath = 'positionSalarieFondsEchDto'

        class item(ItemElement):
            klass = Pocket

            def condition(self):
                return Field('quantity')(self)

            obj_condition = Env('condition')
            obj_availability_date = Env('availability_date')
            obj_amount = CleanDecimal.SI(Dict('mtBrut'))
            obj_quantity = CleanDecimal.SI(Dict('nbParts'))

            def parse(self, obj):
                availability_date = datetime.strptime(obj['dtEcheance'].split('T')[0], '%Y-%m-%d')
                if Env('account_type')(self) in (Account.TYPE_PERCO, Account.TYPE_PER):
                    if availability_date == datetime(2100, 1, 1, 0, 0):
                        availability_date = NotAvailable
                    self.env['availability_date'] = availability_date
                    self.env['condition'] = Pocket.CONDITION_RETIREMENT
                elif availability_date == datetime(2100, 1, 1, 0, 0):
                    self.env['availability_date'] = NotAvailable
                    self.env['condition'] = Pocket.CONDITION_UNKNOWN
                elif availability_date <= datetime.today():
                    # In the past, already available
                    self.env['availability_date'] = availability_date
                    self.env['condition'] = Pocket.CONDITION_AVAILABLE
                else:
                    self.env['availability_date'] = availability_date
                    self.env['condition'] = Pocket.CONDITION_DATE


class AccountsPage(LoggedPage, JsonPage):
    def get_company_name(self):
        json_list = Dict('listPositionsSalarieDispositifsDto')(self.doc)
        if json_list:
            return json_list[0].get('nomEntreprise', NotAvailable)
        return NotAvailable

    @method
    class iter_accounts(DictElement):
        def parse(self, el):
            if not el.get('count', 42):
                raise NoAccountsException()

        item_xpath = "listPositionsSalarieDispositifsDto"

        class item(AccountItemElement):
            pass

    @method
    class iter_investments(InvestDictElement):
        class item(InvestItemElement):
            obj_valuation = CleanDecimal.SI(Dict('mtBrut'))
            obj_quantity = CleanDecimal.SI(Dict('nbParts'))


class AccountHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'operationsIndividuelles'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # We ignore transactions without the status 'Comptabilisé' and
                # transactions related to 'Arbitrage'.
                if (
                    CleanText(Dict('statut'))(self) != 'CPTA'
                    or 'Arbitrage' in Field('label')(self)
                ):
                    return False

                account = Env('account')(self)
                instructions = Dict('instructions')(self)

                if instructions:
                    for ins in instructions:
                        code = CleanText(Dict('codeDispositif', default=''))(ins)

                        if (
                            CleanText(Dict('type'))(ins) != 'ARB'
                            and CleanText(Dict('statut'))(ins) == 'CPTA'
                            and (code == account.id or code in account._linked_accounts)
                        ):
                            return True

                return False

            obj_id = CleanText(Dict('idOpeInd'))
            # Some transactions have no label
            obj_label = Coalesce(
                CleanText(Dict('libelleOperation', default='')),
                CleanText(Dict('libelleCommunication', default='')),
                default=''
            )

            def obj_amount(self):
                total_amount = 0

                for ins in Dict('instructions')(self):
                    if CleanText(Dict('statut'))(ins) == 'ANNULE' or CleanText(Dict('type'))(ins) == 'ARB':
                        continue

                    amount = CleanDecimal.SI(Dict('montantNet', default=None), default=NotAvailable)(ins)

                    if not empty(amount):
                        if CleanText(Dict('type'))(ins) == 'RACH_TIT':
                            total_amount -= amount
                        else:
                            total_amount += amount

                return Decimal.quantize(
                    Decimal(total_amount),
                    Decimal('0.0001'),
                )

            obj_date = obj_rdate = Date(CleanText(Dict('dateComptabilisation')))


class AmundiInvestmentsPage(LoggedPage, HTMLPage):
    def get_tab_url(self, tab_id):
        return Format(
            '/%s%d',
            Regexp(
                CleanText('//script[contains(text(), "Product.init")]'),
                r'(fr_part/ezjscore.*_productsheet_tab_).*AJAX',
                default=None
            ),
            tab_id
        )(self.doc)

    def get_details_url(self):
        return self.get_tab_url(5)

    def get_performance_url(self):
        return self.get_tab_url(2)


class EEInvestmentPage(LoggedPage, HTMLPage):
    def get_recommended_period(self):
        return Title(
            '//label[contains(text(), "Durée minimum de placement")]/following-sibling::span',
            default=NotAvailable,
        )(self.doc)

    def get_details_url(self):
        return Attr('//a[contains(text(), "Caractéristiques")]', 'data-href', default=None)(self.doc)

    def get_performance_url(self):
        return Attr('//a[contains(text(), "Performances")]', 'data-href', default=None)(self.doc)


class InvestmentPerformancePage(LoggedPage, HTMLPage):
    '''
    Note: this class is used to parse a pop-up that contains
    investment details for the regular Amundi website,
    as well as the SG Gestion and the CPR spaces.
    '''

    def get_performance_history(self):
        # The positions of the columns depend on the age of the investment fund.
        # For example, if the fund is younger than 5 years, there will be not '5 ans' column.
        durations = [CleanText('.')(el) for el in self.doc.xpath('//div[contains(@class, "fpPerfglissanteclassique")]//th')]
        values = [CleanText('.')(el) for el in self.doc.xpath('//div[contains(@class, "fpPerfglissanteclassique")]//tr[td[text()="Fonds"]]//td')]
        matches = dict(zip(durations, values))
        # We do not fill the performance dictionary if no performance is available,
        # otherwise it will overwrite the data obtained from the JSON with empty values.
        perfs = {}
        for k, v in {1: '1 an', 3: '3 ans', 5: '5 ans'}.items():
            if matches.get(v):
                perfs[k] = percent_to_ratio(CleanDecimal.French(default=NotAvailable).filter(matches[v]))

        return perfs


class SGGestionPerformancePage(InvestmentPerformancePage):
    pass


class CprPerformancePage(InvestmentPerformancePage):
    pass


class InvestmentDetailPage(LoggedPage, HTMLPage):
    def get_recommended_period(self):
        return Title(
            '//label[contains(text(), "Durée minimum de placement")]/following-sibling::span',
            default=NotAvailable,
        )(self.doc)

    def get_asset_category(self):
        return CleanText(
            '(//label[contains(text(), "Classe d\'actifs")])[1]/following-sibling::span',
            default=NotAvailable
        )(self.doc)


class EEProductInvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        obj_asset_category = CleanText('//span[contains(text(), "Classe")]/following-sibling::span[@class="valeur"][1]')
        obj_recommended_period = CleanText('//span[contains(text(), "Durée minimum")]/following-sibling::span[@class="valeur"][1]')


class AllianzInvestmentPage(LoggedPage, HTMLPage):
    def get_asset_category(self):
        # The format may be a very short description, or be
        # included between quotation marks within a paragraph
        asset_category = CleanText(
            '//div[contains(@class, "fund-summary")]//h3/following-sibling::div',
            default=NotAvailable,
        )(self.doc)
        m = re.search(r'« (.*) »', asset_category)
        if m:
            return m.group(1)
        return asset_category


class EresInvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        obj_asset_category = CleanText(
            '//li[span[contains(text(), "Classification")]]',
            children=False,
            default=NotAvailable,
        )
        obj_recommended_period = CleanText(
            '//li[span[contains(text(), "Durée")]]',
            children=False,
            default=NotAvailable,
        )

        def obj_performance_history(self):
            perfs = {}
            if CleanDecimal.French('(//tr[th[text()="1 an"]]/td[1])[1]', default=None)(self):
                perfs[1] = Eval(lambda x: x / 100, CleanDecimal.French('(//tr[th[text()="1 an"]]/td[1])[1]'))(self)
            if CleanDecimal.French('(//tr[th[text()="3 ans"]]/td[1])[1]', default=None)(self):
                perfs[3] = Eval(lambda x: x / 100, CleanDecimal.French('(//tr[th[text()="3 ans"]]/td[1])[1]'))(self)
            if CleanDecimal.French('(//tr[th[text()="5 ans"]]/td[1])[1]', default=None)(self):
                perfs[5] = Eval(lambda x: x / 100, CleanDecimal.French('(//tr[th[text()="5 ans"]]/td[1])[1]'))(self)
            return perfs


class CprInvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        # Text headers can be in French or in English
        obj_asset_category = Title(
            '//div[contains(text(), "Classe d\'actifs") or contains(text(), "Asset class")]//strong',
            default=NotAvailable,
        )
        obj_recommended_period = Title(
            '//div[contains(text(), "Durée recommandée") or contains(text(), "Recommended duration")]//strong',
            default=NotAvailable,
        )

        def obj_srri(self):
            srri = CleanText('//span[@class="active"]')(self)
            # 'srri' can sometimes be an empty string, so we keep
            # the value scraped on the Amundi website
            return srri or self.obj.srri

    def get_performance_url(self):
        js_script = CleanText('//script[@language="javascript"]')(self.doc)  # beurk
        # Extract performance URL from a string such as 'Product.init(false,"/particuliers..."'
        m = re.search(r'(/particuliers[^\"]+)', js_script)
        if m:
            return 'https://www.cpr-am.fr' + m.group(1)


class BNPInvestmentPage(LoggedPage, HTMLPage):
    def get_fund_id(self):
        return Regexp(
            CleanText('//script[contains(text(), "GLB_ProductId")]'),
            r'GLB_ProductId = "(\w+)',
            default=None
        )(self.doc)


class BNPInvestmentApiPage(LoggedPage, JsonPage):
    @method
    class fill_investment(ItemElement):
        obj_asset_category = Dict('Classification', default=NotAvailable)
        obj_recommended_period = Dict('DureePlacement', default=NotAvailable)


class AxaInvestmentPage(LoggedPage, HTMLPage):
    def get_redirection_params(self):
        params = {}
        params['groupId'] = Regexp(CleanText('//script'), r'getScopeGroupId.*?return \'(\d+)\';')(self.doc)
        params['companyId'] = Regexp(CleanText('//script'), r'getCompanyId.*?return \'(\d+)\';')(self.doc)
        return params

    def get_asset_category(self):
        return Title(CleanText('//th[contains(text(), "Classe")]/following-sibling::td'))(self.doc)


class AxaInvestmentApiPage(LoggedPage, JsonPage):
    def get_api_fund_id(self):
        return Dict('fundData/DALI_PRODUCT_SHARE_ID')(self.doc)

    @method
    class get_asset_category(ItemElement):
        obj_asset_category = CleanText(Dict('fundData/ASSET_CLASS', default=None), default=NotAvailable)

    @method
    class fill_investment(ItemElement):

        def obj_performance_history(self):
            perfs = {}
            perfs[1] = CleanDecimal.French(Dict('rowsData/portfolio/1y'), default=NotAvailable)(self)
            perfs[3] = CleanDecimal.French(Dict('rowsData/portfolio/3y'), default=NotAvailable)(self)
            perfs[5] = CleanDecimal.French(Dict('rowsData/portfolio/5y'), default=NotAvailable)(self)

            for y, p in perfs.items():
                if not empty(p):
                    perfs[y] = p / 100
            return perfs


class EpsensInvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        obj_asset_category = CleanText(
            '//div[div[span[contains(text(), "Classification")]]]/div[2]/span',
            default=NotAvailable,
        )
        obj_recommended_period = CleanText(
            '//div[div[span[contains(text(), "Durée de placement")]]]/div[2]/span',
            default=NotAvailable,
        )


class EcofiInvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        # Recommended period is actually an image so we extract the
        # information from its URL such as '/Horizon/Horizon_5_ans.png'
        obj_recommended_period = Regexp(
            CleanText(Attr('//img[contains(@src, "/Horizon/")]', 'src', default=NotAvailable), replace=[(u'_', ' ')]),
            r'\/Horizon (.*)\.png'
        )
        obj_asset_category = CleanText(
            '//div[contains(text(), "Classification")]/following-sibling::div[1]',
            default=NotAvailable,
        )


class SGGestionInvestmentPage(LoggedPage, HTMLPage):
    @method
    class fill_investment(ItemElement):
        obj_asset_category = CleanText(
            '//label[contains(text(), "Classe d\'actifs")]/following-sibling::span',
            default=NotAvailable,
        )
        obj_recommended_period = CleanText(
            '//label[contains(text(), "Durée minimum")]/following-sibling::span',
            default=NotAvailable,
        )

    def get_performance_url(self):
        return Attr('(//li[@role="presentation"])[1]//a', 'data-href', default=None)(self.doc)


class OlisnetInvestmentPage(LoggedPage, HTMLPage):
    def get_graph_id(self):
        return Regexp(Link('//span[@id="linkDownload"]/a'), r'cs=(\w+)')(self.doc)

    def get_performance(self):
        perf = CleanDecimal.SI(
            Regexp(CleanText('.'), r'Portefeuille : (-?\d+\.?\d*?)%', default=NotAvailable),
            default=NotAvailable
        )(self.doc)

        if empty(perf):
            return NotAvailable
        return perf / 100


class ESAccountsPage(AccountsPage):
    def build_doc(self, content):
        # Rebuild json to match with the json of the other amundi subsites
        content = JsonPage.build_doc(self, content)['listPositionsSalarieFondsDto']
        return {'listPositionsSalarieDispositifsDto': content[0]['positionsSalarieDispositifDto']}

    @method
    class iter_accounts(DictElement):
        item_xpath = 'listPositionsSalarieDispositifsDto'

        class item(AccountItemElement):
            obj_balance = CleanDecimal.SI(Dict('mtBrut'))

    @method
    class iter_investments(InvestDictElement):
        class item(InvestItemElement):
            obj_valuation = CleanDecimal.SI(Dict('mtBrut'))
            obj_quantity = CleanDecimal.SI(Dict('nbParts'))
