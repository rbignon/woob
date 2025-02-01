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

# flake8: compatible

import re

from woob.browser.elements import ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, HasElement, Link, TableCell
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Date, Eval, Field, Regexp
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


class MaintenancePage(HTMLPage):
    def on_load(self):
        raise BrowserUnavailable(CleanText().filter(self.doc.xpath("//p")))


class LoginPage(HTMLPage):
    def on_load(self):
        error_msg = CleanText('//li[@class="globalErreurMessage"]')(self.doc)
        if error_msg:
            # Catch wrongpass accordingly
            wrongpass_messages = ("mot de passe incorrect", "votre compte n'est plus utilisable")
            if any(message in error_msg.lower() for message in wrongpass_messages):
                raise BrowserIncorrectPassword(error_msg)
            raise BrowserUnavailable(error_msg)

    def login(self, login, password):
        form = self.get_form('//form[@id="loginForm"]')
        form["loginForm:name"] = login
        form["loginForm:password"] = password
        form["loginForm:login"] = "loginForm:login"
        form.submit()

    def get_error(self):
        return CleanText('//li[@class="erreurBox"]')(self.doc)


ACCOUNT_TYPES = {
    "Assurance Vie": Account.TYPE_LIFE_INSURANCE,
    "Capitalisation": Account.TYPE_MARKET,
    "Epargne Handicap": Account.TYPE_LIFE_INSURANCE,
    "Unknown": Account.TYPE_UNKNOWN,
    "PERIN": Account.TYPE_PER,
}


class AccountsPage(LoggedPage, HTMLPage):
    def has_multiple_accounts(self):
        return HasElement('//td[text()="Total de votre épargne"]')(self.doc)

    def get_account_id(self):
        return Regexp(CleanText('//span[@class="regleDeCalcul"]'), r"Contrat n° (\d+)")(self.doc)

    def get_switch_account_form(self):
        form = self.get_form(id="syntheseForm")
        form["javax.faces.partial.ajax"] = "true"
        form["javax.faces.source"] = "j_idt64"
        form["javax.faces.partial.execute"] = "@all"
        form["javax.faces.partial.render"] = "syntheseForm"
        form["j_idt64"] = "j_idt64"
        form["syntheseForm"] = "syntheseForm"
        return form

    @method
    class get_account(ItemElement):

        klass = Account

        obj_id = obj_number = Regexp(CleanText('//span[@class="regleDeCalcul"]'), r"Contrat n° (\d+)")
        obj_label = CleanText("//section//h1")
        obj_balance = CleanDecimal.French('//div[table]//span[@class="ea"]')
        obj_currency = Currency('//div[table]//span[@class="ea"]')
        obj_url = Link('//a[text()="Situation du contrat"]')


class TableInvestment(TableElement):
    col_label = re.compile(r"Supports?")
    col_vdate = "Date de valeur"
    col_unitvalue = "Valeur de part"
    col_quantity = "Nombre de parts"
    col_portfolio_share = "%"
    col__gestion_type = re.compile("Nom du profil")


class ItemInvestment(ItemElement):
    klass = Investment

    obj_label = CleanText(TableCell("label"))
    obj_quantity = MyDecimal(TableCell("quantity", default=None))
    obj_unitvalue = MyDecimal(TableCell("unitvalue", default=None))
    obj_vdate = Date(CleanText(TableCell("vdate", default="")), dayfirst=True, default=NotAvailable)
    obj__invest_type = Regexp(CleanText('.//td[contains(text(), "Type")]'), r":[\s]+([\w ]+)", default=NotAvailable)
    obj_code = IsinCode(
        Regexp(CleanText('.//td[contains(text(), "Isin")]'), r":[\s]+([\w]+)", default=NotAvailable),
        default=NotAvailable,
    )
    obj_code_type = IsinType(Field("code"))

    def obj_valuation(self):
        valuation = MyDecimal(TableCell("valuation", default=None))(self)
        h2 = CleanText('./ancestor::div[contains(@id, "Histo")][1]/preceding-sibling::h2[1]')(self)
        if valuation and any(word in h2.lower() for word in self.page.DEBIT_WORDS):
            return -valuation
        return valuation

    def obj_portfolio_share(self):
        ps = MyDecimal(TableCell("portfolio_share", default=None))(self)
        if empty(ps):
            return NotAvailable
        return Eval(lambda x: x / 100, ps)(self)

    def obj__gestion_type(self):
        if self.xpath('ancestor::tbody[ends-with(@id, "contratProfilTable_data")]'):
            # investments are nested in profiles, get profile type
            profile_table_el = self.xpath("ancestor::tr/ancestor::table[position() = 1]")[0]
            profile_table = ProfileTableInvestment(self.page, self, profile_table_el)
            gestion_type = profile_table.get_colnum("_gestion_type")
            assert gestion_type

            path = "ancestor::tr/preceding-sibling::tr[@data-ri][position() = 1][1]/td[%d]" % (gestion_type + 1)
            return CleanText(path)(self)
        return NotAvailable


class ProfileTableInvestment(TableInvestment):
    # used only when portfolio is divided in multiple "profiles"
    head_xpath = '//thead[ends-with(@id, ":contratProfilTable_head")]/tr/th'


class DetailsPage(LoggedPage, HTMLPage):

    def build_doc(self, content):
        # The full transactions page is a broken XML and requires
        # content building to scrap all transactions properly:
        markers = [b"partial-response", b"ongletHistoOperations:ongletHistoriqueOperations"]
        if all(marker in content for marker in markers):
            parts = re.findall(rb"\!\[CDATA\[(.*?)\!\[CDATA\[", content, re.DOTALL)
            return super().build_doc(parts[0])
        return super().build_doc(content)

    DEBIT_WORDS = ["rachat", "frais", "désinvestir"]

    def get_account_data(self):
        # this code is used by iter_accounts
        # and COULD be defined in AccountsPage.iter_accounts with Async
        # but this website disconnect us very often
        raw_label = CleanText('//td[contains(text(), "Option fiscale")]/following-sibling::td')(self.doc)
        xpath = '//td[./span[@id="ongletSituation:infoBullePlusMoinsValueSynthese"]]/..//span[@class="donneeMontant"]'
        val_diff = CleanDecimal.French(xpath)(self.doc)
        data = {
            "valuation_diff": val_diff,
            "_raw_label": raw_label,
            "type": ACCOUNT_TYPES.get(raw_label, Account.TYPE_UNKNOWN),
        }
        return data

    def count_transactions(self):
        return Regexp(CleanText('//span[@class="ui-paginator-current"][1]'), r"(?<=sur )(\d+)", default=None)(self.doc)

    def goto_unitprice(self):
        form = self.get_form(id="ongletSituation:syntheseContrat")
        form["javax.faces.source"] = "ongletSituation:ongletContratTab"
        form["javax.faces.partial.execute"] = "ongletSituation:ongletContratTab"
        form["javax.faces.partial.render"] = "ongletSituation:ongletContratTab"
        form["javax.faces.behavior.event"] = "tabChange"
        form["javax.faces.partial.event"] = "tabChange"
        form["ongletSituation:ongletContratTab_newTab"] = "ongletSituation:ongletContratTab:PRIX_REVIENT_MOYEN"
        form["ongletSituation:ongletContratTab_tabindex"] = "1"
        form.submit()

    @method
    class iter_investment(TableInvestment):
        item_xpath = '//div[contains(@id,"INVESTISSEMENT")]//div[ends-with(@id, ":tableDetailSituationCompte")]//table/tbody/tr[@data-ri]'
        head_xpath = '//div[contains(@id,"INVESTISSEMENT")]//div[ends-with(@id, ":tableDetailSituationCompte")]//table/thead/tr/th'

        col_valuation = re.compile("Contre")

        class item(ItemInvestment):
            def obj_portfolio_share(self):
                inv_share = ItemInvestment.obj_portfolio_share(self)
                if self.xpath('ancestor::tbody[ends-with(@id, "contratProfilTable_data")]'):
                    # investments are nested in profiles, row share is relative to profile share
                    profile_table_el = self.xpath("ancestor::tr/ancestor::table[position() = 1]")[0]
                    profile_table = ProfileTableInvestment(self.page, self, profile_table_el)
                    share_idx = profile_table.get_colnum("portfolio_share")
                    assert share_idx

                    path = "ancestor::tr/preceding-sibling::tr[@data-ri][position() = 1][1]/td[%d]" % (share_idx + 1)

                    profile_share = MyDecimal(path)(self)
                    assert not empty(profile_share), "profile_share is %s" % profile_share
                    profile_share = Eval(lambda x: x / 100, profile_share)(self)
                    return inv_share * profile_share
                else:
                    return inv_share

    @method
    class iter_pm_investment(TableInvestment):
        item_xpath = '//div[contains(@id,"PRIX_REVIENT_MOYEN")]//div[ends-with(@id, ":tableDetailSituationCompte")]//table/tbody/tr[@data-ri]'
        head_xpath = '//div[contains(@id,"PRIX_REVIENT_MOYEN")]//div[ends-with(@id, ":tableDetailSituationCompte")]//table/thead/tr/th'

        col_diff = re.compile(".*PRM en €")
        col_diff_percent = re.compile(".*PRM en %")
        col_unitprice = re.compile(".*Prix de Revient Moyen")

        class item(ItemInvestment):
            obj_diff = MyDecimal(TableCell("diff"), default=NotAvailable)
            obj_diff_ratio = Eval(lambda x: x / 100, MyDecimal(TableCell("diff_percent")))
            obj_unitprice = MyDecimal(TableCell("unitprice"))

            def obj_diff_ratio(self):
                diff_percent = MyDecimal(TableCell("diff_percent"))(self)
                if diff_percent:
                    return diff_percent / 100
                else:
                    return NotAvailable

    def go_historytab(self):
        form = self.get_form(id="ongletSituation:syntheseContrat")
        form["javax.faces.source"] = "tabsPrincipauxConsultationContrat"
        form["javax.faces.partial.execute"] = "tabsPrincipauxConsultationContrat"
        form["javax.faces.partial.render"] = "messageBox+tabsPrincipauxConsultationContrat"
        form["javax.faces.behavior.event"] = "tabChange"
        form["javax.faces.partial.event"] = "tabChange"
        form["tabsPrincipauxConsultationContrat_contentLoad"] = "true"
        form["tabsPrincipauxConsultationContrat_newTab"] = "HISTORIQUE_OPERATIONS"
        form["ongletSituation:ongletContratTab_tabindex"] = "1"
        form.submit()

    def go_historyall(self, page_number):
        form = self.get_form(xpath='//form[contains(@id, "ongletHistoOperations:ongletHistoriqueOperations")]')
        # The form value varies (for example j_idt913 or j_idt62081) so we need to scrape it dynamically.
        # However, sometimes the form does not contain the 'id' attribute, in which case we must reload the page.
        form_value = Attr(
            '//div[@id="ongletHistoOperations:ongletHistoriqueOperations:newoperations"]/div[1]', "id", default=None
        )(self.doc)

        if not form_value:
            return False
        form["javax.faces.partial.ajax"] = "true"
        form["javax.faces.partial.execute"] = form_value
        form["javax.faces.partial.render"] = form_value
        form["javax.faces.source"] = form_value
        form[form_value] = form_value
        form[form_value + "_encodeFeature"] = "true"
        form[form_value + "_pagination"] = "false"
        form[form_value + "_rows"] = "100"
        form[form_value + "_first"] = page_number * 100
        form.submit()
        return True

    @method
    class iter_history(ListElement):
        item_xpath = '//tr[@role="row"]'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText("./td[2]")
            obj_type = Transaction.TYPE_BANK
            obj__index = Attr(".", "data-ri")
            obj_vdate = Date(CleanText("./td[8]"), dayfirst=True)

            def obj_date(self):
                return Date(CleanText("./td[6]", symbols="-"), dayfirst=True, default=Field("vdate")(self))(self)

            def obj_amount(self):
                # We display the raw amount only if the net amount is not available.
                raw_amount = MyDecimal("./td[4]")(self)
                amount = MyDecimal("./td[5]", default=raw_amount)(self)
                if amount and any(word in Field("label")(self).lower() for word in self.page.DEBIT_WORDS):
                    return -amount
                return amount

            def condition(self):
                # We do not scrape "Arrêté annuel" transactions since it is just a yearly synthesis of the contract,
                # nor "Fusion-absorption" transactions because they have no amount.
                return (
                    "Validé" in CleanText("./td[3]")(self)
                    and "Arrêté annuel" not in Field("label")(self)
                    and "Fusion-absorption" not in Field("label")(self)
                )
