# Copyright(C) 2012 Romain Bignon
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
from collections import OrderedDict
from datetime import datetime
from decimal import Decimal
from urllib.parse import urljoin

from requests.cookies import remove_cookie_by_name

from woob.browser.elements import DictElement, ItemElement, ListElement, SkipItem, TableElement, method
from woob.browser.exceptions import ClientError, ServerError
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal,
    CleanText,
    Coalesce,
    Currency,
    Date,
    Env,
    Eval,
    Field,
    Format,
    Lower,
    MapIn,
    Regexp,
)
from woob.browser.pages import FormNotFound, HTMLPage, JsonPage, LoggedPage, pagination
from woob.capabilities.bank import Account, AccountOwnership, AccountOwnerType, Loan, Transfer
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.exceptions import ActionNeeded, BrowserUnavailable, NoAccountsException
from woob.tools.capabilities.bank.iban import is_rib_valid, rib2iban
from woob.tools.capabilities.bank.investments import IsinCode, IsinType, is_isin_valid
from woob.tools.capabilities.bank.transactions import FrenchTransaction

from ..base_pages import BasePage, fix_form


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True)
    return CleanDecimal(*args, **kwargs)


class MyTableCell(TableCell):
    def __init__(self, *names, **kwargs):
        super(MyTableCell, self).__init__(*names, **kwargs)
        self.td = "./tr[%s]/td"


def float_to_decimal(f):
    return Decimal(str(f))


def trunc_decimal(value):
    if not empty(value):
        value = round(value, 4)
    return value


class GarbagePage(LoggedPage, HTMLPage):
    def on_load(self):
        go_back_link = Link('//a[@class="btn" or @class="cta_stroke back"]', default=NotAvailable)(self.doc)

        if go_back_link is not NotAvailable:
            assert len(go_back_link) != 1
            go_back_link = re.search(r"\(~deibaseurl\)(.*)$", go_back_link).group(1)

            self.browser.location("%s%s" % (self.browser.BASEURL, go_back_link))


class MessagePage(GarbagePage):
    def get_message(self):
        return CleanText('//form[contains(@name, "leForm")]//span')(self.doc)

    def submit(self):
        form = self.get_form(name="leForm")

        form["signatur1"] = ["on"]

        form.submit()


class NoAccountCheck:
    def check_no_accounts(self):
        no_account_message = CleanText(
            '//span[@id="MM_LblMessagePopinError"]/p[contains(text(), "Aucun compte disponible")]'
        )(self.doc)

        if no_account_message:
            raise NoAccountsException(no_account_message)


class Transaction(FrenchTransaction):
    PATTERNS = [
        (
            re.compile(r"^CB (?P<text>.*?) FACT (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})\b", re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r"^RET(RAIT)? DAB (?P<dd>\d+)-(?P<mm>\d+)-.*", re.IGNORECASE), FrenchTransaction.TYPE_WITHDRAWAL),
        (
            re.compile(
                r"^RET(RAIT)? DAB (?P<text>.*?) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}) (?P<HH>\d{2})H(?P<MM>\d{2})\b",
                re.IGNORECASE,
            ),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r"^VIR(EMENT)?(\.PERIODIQUE)? (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^PRLV (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^CHEQUE.*", re.IGNORECASE), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(CONVENTION \d+ )?COTIS(ATION)? (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^\* ?(?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^REMISE (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^Depot Esp (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^(?P<text>.*)( \d+)? QUITTANCE .*", re.IGNORECASE), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^CB [\d\*]+ TOT DIF .*", re.IGNORECASE), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r"^CB [\d\*]+ (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_CARD),
        (
            re.compile(r"^CB (?P<text>.*?) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})\b", re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r"\*CB (?P<text>.*?) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})\b", re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r"^FAC CB (?P<text>.*?) (?P<dd>\d{2})/(?P<mm>\d{2})\b", re.IGNORECASE),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r"^\*?CB (?P<text>.*)", re.IGNORECASE), FrenchTransaction.TYPE_CARD),
        # For life insurances and capitalisation contracts
        (re.compile(r"^VERSEMENT", re.IGNORECASE), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^Réinvestissement", re.IGNORECASE), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^REVALORISATION", re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^ARBITRAGE", re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^RACHAT PARTIEL", re.IGNORECASE), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^(?P<text>INTERETS.*)", re.IGNORECASE), FrenchTransaction.TYPE_BANK),
    ]


class IndexPage(LoggedPage, BasePage, NoAccountCheck):
    ACCOUNT_TYPES = {
        "Epargne liquide": Account.TYPE_SAVINGS,
        "Compte Courant": Account.TYPE_CHECKING,
        "COMPTE A VUE": Account.TYPE_CHECKING,
        "COMPTE CHEQUE": Account.TYPE_CHECKING,
        "Mes comptes": Account.TYPE_CHECKING,
        "CPT DEPOT PART.": Account.TYPE_CHECKING,
        "CPT DEPOT PROF.": Account.TYPE_CHECKING,
        "Mon épargne": Account.TYPE_SAVINGS,
        "Mes autres comptes": Account.TYPE_SAVINGS,
        "Compte Epargne et DAT": Account.TYPE_SAVINGS,
        "Plan et Contrat d'Epargne": Account.TYPE_SAVINGS,
        "COMPTE SUR LIVRET": Account.TYPE_SAVINGS,
        "LIVRET DEV.DURABLE": Account.TYPE_SAVINGS,
        "LDD Solidaire": Account.TYPE_SAVINGS,
        "LIVRET A": Account.TYPE_SAVINGS,
        "LIVRET JEUNE": Account.TYPE_SAVINGS,
        "LIVRET GRAND PRIX": Account.TYPE_SAVINGS,
        "LEP": Account.TYPE_SAVINGS,
        "L.EPAR POPULAIRE": Account.TYPE_SAVINGS,
        "LEL": Account.TYPE_SAVINGS,
        "PLAN EPARG. LOGEMENT": Account.TYPE_SAVINGS,
        "L. EPAR LOGEMENT": Account.TYPE_SAVINGS,
        "CPT PARTS SOCIALES": Account.TYPE_MARKET,
        "PEL": Account.TYPE_SAVINGS,
        "PEL 16 2013": Account.TYPE_SAVINGS,
        "PEL 16 2014": Account.TYPE_SAVINGS,
        "PARTS SOCIALES": Account.TYPE_MARKET,
        "Titres": Account.TYPE_MARKET,
        "Compte titres": Account.TYPE_MARKET,
        "Mes crédits immobiliers": Account.TYPE_MORTGAGE,
        "Mes crédits renouvelables": Account.TYPE_REVOLVING_CREDIT,
        "Mes crédits consommation": Account.TYPE_CONSUMER_CREDIT,
        "PEA NUMERAIRE": Account.TYPE_PEA,
        "COMPTE NUMERAIRE PEA": Account.TYPE_PEA,
        "PEA": Account.TYPE_PEA,
        "primo": Account.TYPE_MORTGAGE,
        "equipement": Account.TYPE_LOAN,
        "garanti par l'état": Account.TYPE_LOAN,
        "credits de tresorerie": Account.TYPE_LOAN,
    }

    ACCOUNT_TYPES_LINK = {
        "SYNTHESE_ASSURANCE_CNP": Account.TYPE_LIFE_INSURANCE,
        "REDIR_ASS_VIE": Account.TYPE_LIFE_INSURANCE,
        "SYNTHESE_EPARGNE": Account.TYPE_LIFE_INSURANCE,
        "ASSURANCE_VIE": Account.TYPE_LIFE_INSURANCE,
        "NA_WEB": Account.TYPE_LIFE_INSURANCE,
        "BOURSE": Account.TYPE_MARKET,
        "COMPTE_TITRE": Account.TYPE_MARKET,
    }

    ACCOUNT_OWNER_TYPE = {
        "personnel": AccountOwnerType.PRIVATE,
        "particulier": AccountOwnerType.PRIVATE,
        "professionnel": AccountOwnerType.ORGANIZATION,
    }

    def on_load(self):

        # For now, we have to handle this because after this warning message,
        # the user is disconnected (even if all others account are reachable)
        if "QCF" in self.browser.url:
            # QCF is a mandatory test to make sure you know the basics about financials products
            # however, you can still choose to postpone it. hence the continue link
            link = Link('//span[@id="lea-prdvel-lien"]//b/a[contains(text(), "Continuer")]')(self.doc)
            if link:
                self.logger.warning("By-passing QCF")
                self.browser.location(link)
            else:
                message = CleanText('//span[contains(@id, "QCF")]/p')(self.doc)
                expected = (
                    "investissement financier (QCF) n’est plus valide à ce jour ou que vous avez refusé d’y répondre",
                    "expérience en matière d'instruments financiers n'est plus valide ou n’a pas pu être déterminé",
                )
                if any(e in message for e in expected):
                    raise ActionNeeded(message)
                raise AssertionError("Unhandled error while going to market space: %s" % message)

        message = CleanText(
            '//body/div[@class="content"]//p[contains(text(), "indisponible pour cause de maintenance")]'
        )(self.doc)
        if message:
            raise BrowserUnavailable(message)

        # This page is sometimes an useless step to the market website.
        bourse_link = Link(
            '//div[@id="MM_COMPTE_TITRE_pnlbourseoic"]//a[contains(text(), "Accédez à la consultation")]', default=None
        )(self.doc)

        if bourse_link:
            self.browser.location(bourse_link)

    def need_auth(self):
        return bool(CleanText('//span[contains(text(), "Authentification non rejouable")]')(self.doc))

    def check_no_loans(self):
        return not any(
            (
                CleanText('//table[@class="menu"]//div[contains(., "Crédits")]')(self.doc),
                CleanText('//table[@class="header-navigation_main"]//a[contains(@href, "CRESYNT0")]')(self.doc),
            )
        )

    def check_measure_accounts(self):
        return not CleanText('//div[@class="MessageErreur"]/ul/li[contains(text(), "Aucun compte disponible")]')(
            self.doc
        )

    def find_and_replace(self, info, acc_id):
        # The site might be broken: id in js: 4097800039137N418S00197, id in title: 1379418S001 (N instead of 9)
        # So we seek for a 1 letter difference and replace if found .... (so sad)
        for i in range(len(info["id"]) - len(acc_id) + 1):
            sub_part = info["id"][i : i + len(acc_id)]
            z = zip(sub_part, acc_id)
            if len([tuple_letter for tuple_letter in z if len(set(tuple_letter)) > 1]) == 1:
                info["link"] = info["link"].replace(sub_part, acc_id)
                info["id"] = info["id"].replace(sub_part, acc_id)
                return

    def _get_account_info(self, a, accounts):
        m = re.search(
            r"PostBack(Options)?\([\"'][^\"']+[\"'],\s*['\"]([HISTORIQUE_\w|SYNTHESE_ASSURANCE_CNP|BOURSE|COMPTE_TITRE][\d\w&]+)?['\"]",
            a.attrib.get("href", ""),
        )

        if m is None:
            return None
        else:
            # it is in form CB&12345[&2]. the last part is only for new website
            # and is necessary for navigation.
            link = m.group(2)
            parts = link.split("&")
            info = {}
            info["link"] = link
            id = re.search(r"([\d]+)", a.attrib.get("title", ""))
            if len(parts) > 1:
                info["type"] = parts[0]
                if info["type"] in ("REDIR_ASS_VIE", "NA_WEB"):
                    # The link format for these account types has an additional parameter
                    info["id"] = info["_id"] = parts[2]
                else:
                    info["id"] = info["_id"] = parts[1]
                if id or info["id"] in [acc._info["_id"] for acc in accounts.values()]:
                    if id:
                        _id = id.group(1)
                    else:
                        unique_ids = {k for k, v in accounts.items() if info["id"] == v._info["_id"]}
                        _id = list(unique_ids)[0]
                    self.find_and_replace(info, _id)
            else:
                if id is None:
                    return None
                info["type"] = link
                info["id"] = info["_id"] = id.group(1)
            account_type = self.ACCOUNT_TYPES_LINK.get(info["type"])
            if account_type:
                info["acc_type"] = account_type
            return info

    def is_account_inactive(self, account_id):
        return self.doc.xpath('//tr[td[contains(text(), $id)]][@class="Inactive"]', id=account_id)

    def _add_account(
        self, accounts, link, label, account_type, balance, number=None, ownership=NotAvailable, owner_type=NotAvailable
    ):
        info = self._get_account_info(link, accounts)
        if info is None:
            self.logger.warning("Unable to parse account %r: %r" % (label, link))
            return

        account = Account()
        account._card_links = None
        account.id = info["id"]
        if is_rib_valid(info["id"]):
            account.iban = rib2iban(info["id"])
        account._info = info
        account.number = number
        account.label = label
        account.ownership = ownership
        account.type = self.ACCOUNT_TYPES.get(label, info.get("acc_type", account_type))
        account.owner_type = owner_type
        if "PERP" in account.label:
            account.type = Account.TYPE_PERP
        if "NUANCES CAPITALISATI" in account.label:
            account.type = Account.TYPE_CAPITALISATION
        if account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_PERP):
            account.ownership = AccountOwnership.OWNER

        if not balance:
            try:
                balance = self.get_balance(account)
            except BrowserUnavailable as e:
                if "erreur_technique" in e.response.url:
                    # Details account are not accessible and navigation is broken here
                    # This account must be skipped
                    self.logger.warning("Could not access to %s details: we skip it", account.label)
                    self.browser.do_login()
                    return
                raise

        if not empty(balance):
            account.balance = Decimal(FrenchTransaction.clean_amount(balance))
            account.currency = account.get_currency(balance)
        else:
            account.currency = account.balance = NotAvailable

        account._card_links = []

        # Set coming history link to the parent account. At this point, we don't have card account yet.
        if account._info["type"] == "HISTORIQUE_CB" and account.id in accounts:
            a = accounts[account.id]
            a.coming = Decimal("0.0")
            a._card_links = account._info
            return

        accounts[account.id] = account
        return account

    def get_balance(self, account):
        if account.type not in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_PERP, Account.TYPE_CAPITALISATION):
            return NotAvailable
        page = self.go_history(account._info).page
        balance = page.doc.xpath(
            './/tr[td[contains(@id,"NumContrat")]]/td[@class="somme"]/a[contains(@href, $id)]', id=account.id
        )
        if len(balance) > 0:
            balance = CleanText(".")(balance[0])
            if balance == "":
                balance = NotAvailable
        else:
            # Specific xpath for some Life Insurances:
            balance = page.doc.xpath('//tr[td[contains(text(), $id)]]/td/div[contains(@id, "Solde")]', id=account.id)
            if len(balance) > 0:
                balance = CleanText(".")(balance[0])
                if balance == "":
                    balance = NotAvailable
            else:
                # sometimes the accounts are attached but no info is available
                balance = NotAvailable
        self.go_list()
        return balance

    def get_measure_balance(self, account):
        for tr in self.doc.xpath('//table[@cellpadding="1"]/tr[not(@class)]'):
            account_number = CleanText('./td/a[contains(@class, "NumeroDeCompte")]')(tr)
            if re.search(r"[A-Z]*\d{3,}", account_number).group() in account.id:
                # The regex '\s\d{1,3}(?:[\s.,]\d{3})*(?:[\s.,]\d{2})' matches for example '106 100,64'
                return re.search(r"\s\d{1,3}(?:[\s.,]\d{3})*(?:[\s.,]\d{2})", account_number).group()
        return NotAvailable

    def get_measure_ids(self):
        accounts_id = []
        for a in self.doc.xpath('//table[@cellpadding="1"]/tr/td[2]/a'):
            accounts_id.append(re.search(r"(\d{4,})", Attr(".", "href")(a)).group(1))
        return accounts_id

    def has_next_page(self):
        return self.doc.xpath(
            '//div[@id="MM_SYNTHESE_MESURES_m_DivLinksPrecSuiv"]//a[contains(text(), "Page suivante")]'
        )

    def goto_next_page(self):
        form = self.get_form(id="main")

        form["__EVENTTARGET"] = "MM$SYNTHESE_MESURES$lnkSuivante"
        form["__EVENTARGUMENT"] = ""
        form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$SYNTHESE_MESURES$lnkSuivante"
        fix_form(form)
        form.submit()

    def get_list(self, owner_name):
        accounts = OrderedDict()

        # Old website
        self.browser.new_website = False
        for table in self.doc.xpath('//table[@cellpadding="1"]'):
            account_type = Account.TYPE_UNKNOWN
            owner_type = self.get_owner_type(table.attrib.get("id"))

            for tr in table.xpath("./tr"):
                tds = tr.findall("td")
                if tr.attrib.get("class", "") == "DataGridHeader":
                    account_type = (
                        self.ACCOUNT_TYPES.get(tds[1].text.strip())
                        or self.ACCOUNT_TYPES.get(CleanText(".")(tds[2]))
                        or self.ACCOUNT_TYPES.get(CleanText(".")(tds[3]), Account.TYPE_UNKNOWN)
                    )
                else:
                    # On the same row, there could have many accounts (check account and a card one).
                    # For the card line, the number will be the same than the checking account, so we skip it.
                    ownership = self.get_ownership(tds, owner_name)
                    if len(tds) > 4:
                        for i, a in enumerate(tds[2].xpath("./a")):
                            label = CleanText(".")(a)
                            balance = CleanText(".")(tds[-2].xpath("./a")[i])
                            number = None
                            # if i > 0, that mean it's a card account. The number will be the same than it's
                            # checking parent account, we have to skip it.
                            if i == 0:
                                number = CleanText(".")(tds[-4].xpath("./a")[0])
                            self._add_account(
                                accounts,
                                a,
                                label,
                                account_type,
                                balance,
                                number,
                                ownership=ownership,
                                owner_type=owner_type,
                            )
                    # Only 4 tds on "banque de la reunion" website.
                    elif len(tds) == 4:
                        for i, a in enumerate(tds[1].xpath("./a")):
                            label = CleanText(".")(a)
                            balance = CleanText(".")(tds[-1].xpath("./a")[i])
                            self._add_account(
                                accounts, a, label, account_type, balance, ownership=ownership, owner_type=owner_type
                            )

        website = "old"
        if accounts:
            website = "new"
        self.logger.debug("we are on the %s website", website)

        if len(accounts) == 0:
            # New website
            self.browser.new_website = True
            owner_type = self.get_owner_type()
            for table in self.doc.xpath('//div[@class="panel"]'):
                title = table.getprevious()
                if title is None:
                    continue
                account_type = self.ACCOUNT_TYPES.get(CleanText(".")(title), Account.TYPE_UNKNOWN)
                for tr in table.xpath('.//tr[@class!="en-tetes" and @class!="Inactive"]'):
                    tds = tr.findall("td")
                    for i in range(len(tds)):
                        a = tds[i].find(".//a")
                        if a is not None:
                            break

                    if a is None:
                        continue

                    # sometimes there's a tooltip span to ignore next to <strong>
                    # (perhaps only on creditcooperatif)
                    label = CleanText(".//strong")(tds[0])
                    balance = CleanText('.//td[has-class("somme")]')(tr)
                    ownership = self.get_ownership(tds, owner_name)
                    account = self._add_account(
                        accounts, a, label, account_type, balance, ownership=ownership, owner_type=owner_type
                    )
                    if account:
                        account.number = CleanText(".")(tds[1])

                        # for natixis accounts, the number is also the REST api path
                        # leading to the natixis account seen as a REST resource
                        account._natixis_url_path = None
                        m = re.search(
                            r"([A-Z]{3})([A-Z]{2}|[A-Z]{1}[0-9]{1})(\d{6})", account.number
                        )  # ex: PERIC123456, PERCE312312, ESSEN789789 OR INFI2000000, ESSE2111111
                        if m:
                            account._natixis_url_path = "/{}/{}/{}".format(*m.groups())
        return list(accounts.values())

    def get_ownership(self, tds, owner_name):
        if len(tds) > 2:
            account_owner = CleanText(".", default=None)(tds[2]).upper()
            if account_owner and any(title in account_owner for title in ("M", "MR", "MLLE", "MLE", "MME")):
                pattern = re.compile(
                    r"(m|mr|me|mme|mlle|mle|ml)\.? ?(.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)", re.IGNORECASE
                )

                if pattern.search(account_owner):
                    return AccountOwnership.CO_OWNER
                elif all(n in account_owner for n in owner_name.split()):
                    return AccountOwnership.OWNER
                return AccountOwnership.ATTORNEY
        return NotAvailable

    def get_owner_type(self, text=None):
        owner_type = None
        if text:
            # If we have something to use for finding the owner_type, we use that.
            owner_type = self.deduce_owner_type(text)
        if not owner_type:
            # If we have not found yet, we use the current client space name.
            header_title = CleanText('//a[@id="header-market_title"]')(self.doc)
            owner_type = self.deduce_owner_type(header_title)
        return owner_type

    def deduce_owner_type(self, text):
        if not text:
            text = ""
        text = text.lower()
        owner_type = MapIn(None, self.ACCOUNT_OWNER_TYPE, default=NotAvailable).filter(text)
        if not owner_type:
            self.logger.warning("Could not find the owner_type")
        return owner_type

    def is_access_error(self):
        error_message = "Vous n'êtes pas autorisé à accéder à cette fonction"
        if error_message in CleanText('//div[@class="MessageErreur"]')(self.doc):
            return True

        return False

    def prepare_form_cons_or_revolving(self, tr, loan):
        if loan == "revolving":
            td_id = "IdaCreditPerm"
            pattern = r"CREDITCONSO&(\w+)"
            form_argument = "ACTIVDESACT_CREDITCONSO&"
        else:
            td_id = "IdPopinLink"
            pattern = r"SAV_PRETS_PERSONNELS&(\w+[&]?\w+)"
            form_argument = "SAV_PRETS_PERSONNELS&"

        argument_id = Regexp(
            Link(f"./td/a[contains(@id, {td_id})]"),
            pattern,
        )(tr)

        form = self.get_form(id="main")

        eventargument = f"{form_argument}{argument_id}"
        eventtarget = "MM$SYNTHESE_CREDITS"
        scriptmanager = "MM$m_UpdatePanel|MM$SYNTHESE_CREDITS"

        return form, eventargument, eventtarget, scriptmanager

    def prepare_form_old_loan_website(self, td):
        argument = Regexp(
            Link("./a", default=""),
            r"(CREDIT_DETAILS_\w+&.*?)\"",
            default=None,
        )(td)

        form = self.get_form(id="main")

        eventargument = argument
        scriptmanager = "MM$m_UpdatePanel|MM$SYNTHESE_CREDITS"
        eventtarget = "MM$SYNTHESE_CREDITS"

        return form, eventargument, eventtarget, scriptmanager

    def is_old_loan_website(self):
        return CleanText('//table[@cellpadding="1"]/tr[not(@class) and td[a]]')(self.doc)

    @method
    class fill_old_loan(ItemElement):
        obj_total_amount = CleanDecimal.French(
            '//tr[td[span[contains(text(), "Capital emprunté")]]]/td[5]', default=NotAvailable
        )
        obj_rate = CleanDecimal.French('//tr[td[span[contains(text(), "Taux")]]]/td[5]', default=NotAvailable)
        obj_maturity_date = Date(
            CleanText('//tr[td[span[contains(text(), "Dernière échéance")]]]/td[5]'),
            dayfirst=True,
            default=NotAvailable,
        )
        obj_next_payment_amount = CleanDecimal.French(
            '//tr[td[span[contains(text(), "Montant prochaine")]]]/td[5]',
            default=NotAvailable,
        )
        obj_next_payment_date = Date(
            CleanText('//tr[td[span[contains(text(), "Prochaine échéance")]]]/td[5]'),
            dayfirst=True,
            default=NotAvailable,
        )

    def get_loan_list(self):
        accounts = OrderedDict()

        # Old website
        for tr in self.doc.xpath('//table[@cellpadding="1"]/tr[not(@class) and td[a]]'):
            tds = tr.findall("td")

            if "Veuillez contacter le Crédit Bailleur" in CleanText("./a")(tds[4]):
                # balance not available, we skip the account
                continue

            account = Loan()
            account._card_links = None
            account.id = account.number = CleanText("./a")(tds[2]).split("-")[0].strip()
            account.label = CleanText("./a")(tds[2]).split("-")[-1].strip()
            account.type = MapIn(None, self.ACCOUNT_TYPES, Account.TYPE_UNKNOWN).filter(Lower().filter(account.label))
            account.balance = -CleanDecimal("./a", replace_dots=True)(tds[4])
            account.currency = account.get_currency(CleanText("./a")(tds[4]))
            account.owner_type = self.get_owner_type(tr.attrib.get("id"))
            account._form_params = self.prepare_form_old_loan_website(tds[2])

            if not account._form_params:
                # In this case the loan is pre-approved but there is no information about it so we skip it.
                continue

            if account.type == Account.TYPE_UNKNOWN:
                self.logger.warning("Loan %s is untyped, please type it.", account.label)
                account.type = Account.TYPE_LOAN

            accounts[account.id] = account

        website = "new"
        if accounts:
            website = "old"
            self.logger.warning("we are on the old website")

        if website == "new":
            # New website
            owner_type = self.get_owner_type()
            for table in self.doc.xpath('//div[@class="panel"]'):
                title = table.getprevious()
                if title is None:
                    continue
                account_type = self.ACCOUNT_TYPES.get(CleanText(".")(title), Account.TYPE_UNKNOWN)

                for tr in table.xpath(
                    './table/tbody/tr[contains(@id,"MM_SYNTHESE_CREDITS") and contains(@id,"IdTrGlobal")]'
                ):
                    tds = tr.findall("td")
                    if not tds:
                        continue
                    label = CleanText("(.//a/strong)[1]", children=False)(tds[0])

                    # The balance column is not always in the same position for children modules.
                    # So check for it's position by name. If not finding, we do it the old way, using the last column.
                    # We search at tr level to avoid fetching balance column in previous sections of the table.
                    balance_col_exist = bool(
                        tr.xpath(
                            './preceding-sibling::tr[@class="en-tetes"]/th[contains(text(), "Capital restant dû")]'
                        )
                    )
                    if balance_col_exist:
                        balance_col_id = int(
                            tr.xpath(
                                'count(./preceding-sibling::tr[@class="en-tetes"]/th[contains(text(), "Capital restant dû")]/preceding-sibling::*)'
                            )
                        )
                        balance = CleanDecimal.French(".", sign="-")(tds[balance_col_id])
                    else:
                        balance = CleanDecimal.French(".", sign="-")(tds[-1])

                    if len(tds) == 3:
                        available = CleanDecimal.French(".")(tds[-2])

                        if available and not any(cls in Attr(".", "id")(tr) for cls in ["dgImmo", "dgConso"]):
                            # In case of Consumer credit or revolving credit, we add available amount with max amount
                            # (which is negative) to get what was spend. Example: 'Disponible' -> available = +8000,
                            # 'Crédit maximum autorisé' -> balance = -8000, final balance = 0.
                            balance = available + balance

                    account = Loan()
                    account.id = account.number = label.split(" ")[-1]
                    account.label = label
                    account.type = account_type
                    account.balance = balance
                    account.currency = account.get_currency(CleanText(".")(tds[-1]))
                    account.owner_type = owner_type
                    account._card_links = []
                    # The website doesn't show any information relative to the loan
                    # owner, we can then assume they all belong to the credentials owner.
                    account.ownership = AccountOwnership.OWNER

                    # Loans details are on the current page
                    if "immobiliers" in CleanText(".")(title) or (
                        "consommation" in CleanText(".")(title)
                        and not Link('./td/a[contains(@id, "IdPopinLink")]', default=None)(tr)
                    ):
                        # Each row contains a `th` with a label and one `td` with the value
                        value_xpath = './/div[contains(@id, "_IdDivDetail_")]//tr[contains(@id, "_Id%s_")]/td'
                        account.total_amount = CleanDecimal.French(
                            value_xpath % "CapitalEmprunte",
                            default=NotAvailable,
                        )(tr)
                        account.rate = CleanDecimal.French(value_xpath % "Taux", default=NotAvailable)(tr)
                        account.opening_date = Date(
                            CleanText(value_xpath % "DateOuverture"),
                            dayfirst=True,
                            default=NotAvailable,
                        )(tr)
                        account.subscription_date = Date(
                            CleanText(value_xpath % "DateSignature"),
                            dayfirst=True,
                            default=NotAvailable,
                        )(tr)
                        account.maturity_date = Date(
                            CleanText(value_xpath % "DerniereEcheance"),
                            dayfirst=True,
                            default=NotAvailable,
                        )(tr)
                        account.next_payment_amount = CleanDecimal.French(
                            value_xpath % "MontantEcheance",
                            default=NotAvailable,
                        )(tr)
                        account.next_payment_date = Date(
                            CleanText(value_xpath % "DateProchaineEcheance"),
                            dayfirst=True,
                            default=NotAvailable,
                        )(tr)

                    elif "consommation" in CleanText(".")(title):
                        form_params = self.prepare_form_cons_or_revolving(tr, "conso")
                        self.submit_form(*form_params)
                        details_conso = self.browser.go_details_revolving_or_cons(loan_type="cons")

                        account.label = CleanText(Dict("offreCredit/produit/libelle", default=account.label))(
                            details_conso
                        )
                        account.number = CleanText(Dict("numDossier", default=NotAvailable), default=NotAvailable)(
                            details_conso
                        )
                        account.total_amount = CleanDecimal.SI(Dict("offreCredit/capitalEmprunte"))(details_conso)
                        account.rate = trunc_decimal(
                            CleanDecimal.SI(Dict("offreCredit/taeg", default=NotAvailable), default=NotAvailable)(
                                details_conso
                            )
                        )
                        account.iban = Dict("domiciliationBancaire/codeIban", default=NotAvailable)(details_conso)
                        account.next_payment_amount = CleanDecimal.SI(
                            Dict("montantProchaineEcheance", default=NotAvailable), default=NotAvailable
                        )(details_conso)
                        account.insurance_label = CleanText(
                            Dict("souscripteur/libelle", default=""), default=NotAvailable
                        )(details_conso)
                        account.insurance_amount = CleanDecimal.SI(
                            Dict("souscripteur/prime", default=NotAvailable), default=NotAvailable
                        )(details_conso)
                        account.insurance_rate = trunc_decimal(
                            CleanDecimal.SI(Dict("souscripteur/taux", default=NotAvailable), default=NotAvailable)(
                                details_conso
                            )
                        )

                        loan_dates = {
                            "maturity_date": "dateFin",
                            "next_payment_date": "dateProchaineEcheance",
                            "subscription_date": "dateSignature",
                        }
                        for k, v in loan_dates.items():
                            date = Dict(v, default=NotAvailable)(details_conso)
                            if not empty(date):
                                if date > 0:
                                    date = datetime.fromtimestamp(date / 1000)
                                else:
                                    date = NotAvailable
                            setattr(account, k, date)

                    elif "renouvelables" in CleanText(".")(title):
                        # To access the life insurance space, we need to delete the JSESSIONID cookie
                        # to avoid an expired session
                        # There might be duplicated JSESSIONID cookies (eg with different paths),
                        # that's why we use remove_cookie_by_name()
                        remove_cookie_by_name(self.browser.session.cookies, "JSESSIONID")

                        try:
                            form_params = self.prepare_form_cons_or_revolving(tr, "revolving")
                            self.submit_form(*form_params)

                        except ClientError as e:
                            if e.response.status_code == 401:
                                raise ActionNeeded(
                                    "La situation actuelle de votre dossier ne vous permet pas d'accéder à cette fonctionnalité. "
                                    + "Nous vous invitons à contacter votre Centre de relation Clientèle pour accéder à votre prêt."
                                )
                            raise
                        d = self.browser.go_details_revolving_or_cons(loan_type="revolving")
                        if d:
                            account.total_amount = float_to_decimal(d["contrat"]["creditMaxAutorise"])
                            account.available_amount = float_to_decimal(d["situationCredit"]["disponible"])
                            account.used_amount = abs(account.balance)
                            # next_payment_amount has always a default value
                            # fetch it, only when revolving has been used
                            if account.balance != 0:
                                account.next_payment_amount = float_to_decimal(
                                    d["situationCredit"]["mensualiteEnCours"]
                                )
                    accounts[account.id] = account
        return list(accounts.values())

    def submit_form(self, form, eventargument, eventtarget, scriptmanager):
        form["__EVENTARGUMENT"] = eventargument
        form["__EVENTTARGET"] = eventtarget
        form["m_ScriptManager"] = scriptmanager
        fix_form(form)

        # For Pro users, after several redirections, leading to GarbagePage,
        # baseurl can be back to Par users URL, when this form must be submitted.
        self.browser.url = urljoin(self.browser.BASEURL, form.url)
        try:
            form.submit()
        except ServerError as err:
            if err.response.status_code in (500, 503):
                raise BrowserUnavailable()
            raise

    def get_partial_accounts_error_message(self):
        # Found on some accounts:
        # > En raison d'un dysfonctionnement technique, une partie de vos
        # > contrats peut ne pas être visible. Nous nous attachons à les
        # > rendre visibles dans les meilleurs délais.
        return CleanText(
            '//div[@id="MM_SYNTHESE_CREDITS_divPopinInfoIndispo"]//p[1]',
        )(self.doc)

    def submit_conso_details(self):
        self.get_form(id="SAV_PP").submit()

    def go_levies(self, account_id=None):
        form = self.get_form(id="main")
        if account_id:
            # Go to an account specific levies page
            eventargument = ""
            if "MM$m_CH$IsMsgInit" in form:
                # Old website
                form["MM$SYNTHESE_SDD_RECUS$m_ExDropDownList"] = account_id
                eventtarget = "MM$SYNTHESE_SDD_RECUS$m_ExDropDownList"
                scriptmanager = "MM$m_UpdatePanel|MM$SYNTHESE_SDD_RECUS$m_ExDropDownList"
            else:
                # New website
                form["MM$SYNTHESE_SDD_RECUS$ddlCompte"] = account_id
                eventtarget = "MM$SYNTHESE_SDD_RECUS$ddlCompte"
                scriptmanager = "MM$m_UpdatePanel|MM$SYNTHESE_SDD_RECUS$ddlCompte"
            self.submit_form(
                form,
                eventargument,
                eventtarget,
                scriptmanager,
            )
        else:
            # Go to an general levies page page where all levies are found
            if "MM$m_CH$IsMsgInit" in form:
                # Old website
                eventargument = "SDDRSYN0"
                eventtarget = "Menu_AJAX"
                scriptmanager = "m_ScriptManager|Menu_AJAX"
            else:
                # New website
                eventargument = "SDDRSYN0&codeMenu=WPS1"
                eventtarget = "MM$Menu_Ajax"
                scriptmanager = "MM$m_UpdatePanel|MM$Menu_Ajax"
            self.submit_form(
                form,
                eventargument,
                eventtarget,
                scriptmanager,
            )

    def go_list(self):

        form = self.get_form(id="main")
        eventargument = "CPTSYNT0"

        if "MM$m_CH$IsMsgInit" in form:
            # Old website
            eventtarget = "Menu_AJAX"
            scriptmanager = "m_ScriptManager|Menu_AJAX"
        else:
            # New website
            eventtarget = "MM$m_PostBack"
            scriptmanager = "MM$m_UpdatePanel|MM$m_PostBack"

        self.submit_form(form, eventargument, eventtarget, scriptmanager)

    def go_cards(self):
        # Do not try to go the card summary if we have no card, it breaks the session
        if self.browser.new_website and not CleanText('//form[@id="main"]//a/span[text()="Mes cartes bancaires"]')(
            self.doc
        ):
            self.logger.info("Do not try to go the CardsPage, there is not link on the main page")
            return

        form = self.get_form(id="main")

        eventargument = ""

        if "MM$m_CH$IsMsgInit" in form:
            # Old website
            eventtarget = "Menu_AJAX"
            eventargument = "HISENCB0"
            scriptmanager = "m_ScriptManager|Menu_AJAX"
        else:
            # New website
            eventtarget = "MM$SYNTHESE$btnSyntheseCarte"
            scriptmanager = "MM$m_UpdatePanel|MM$SYNTHESE$btnSyntheseCarte"

        self.submit_form(form, eventargument, eventtarget, scriptmanager)

    # only for old website
    def go_card_coming(self, eventargument):
        form = self.get_form(id="main")
        eventtarget = "MM$HISTORIQUE_CB"
        scriptmanager = "m_ScriptManager|Menu_AJAX"
        self.submit_form(form, eventargument, eventtarget, scriptmanager)

    # only for new website
    def go_coming(self, eventargument):
        form = self.get_form(id="main")
        eventtarget = "MM$HISTORIQUE_CB"
        scriptmanager = "MM$m_UpdatePanel|MM$HISTORIQUE_CB"
        self.submit_form(form, eventargument, eventtarget, scriptmanager)

    # On some pages, navigate to indexPage does not lead to the list of measures, so we need this form ...
    def go_measure_list(self):
        form = self.get_form(id="main")

        form["__EVENTARGUMENT"] = "MESLIST0"
        form["__EVENTTARGET"] = "Menu_AJAX"
        form["m_ScriptManager"] = "m_ScriptManager|Menu_AJAX"

        fix_form(form)

        form.submit()

    # This function goes to the accounts page of one measure giving its id
    def go_measure_accounts_list(self, measure_id):
        form = self.get_form(id="main")

        form["__EVENTARGUMENT"] = "CPTSYNT0"

        if "MM$m_CH$IsMsgInit" in form:
            # Old website
            form["__EVENTTARGET"] = "MM$SYNTHESE_MESURES"
            form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$SYNTHESE_MESURES"
            form["__EVENTARGUMENT"] = measure_id
        else:
            # New website
            form["__EVENTTARGET"] = "MM$m_PostBack"
            form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$m_PostBack"

        fix_form(form)

        form.submit()

    def go_loan_list(self):
        form = self.get_form(id="main")

        form["__EVENTARGUMENT"] = "CRESYNT0"

        if "MM$m_CH$IsMsgInit" in form:
            # Old website
            pass
        else:
            # New website
            form["__EVENTTARGET"] = "MM$m_PostBack"
            form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$m_PostBack"

        fix_form(form)

        form.submit()

    def go_checkings(self):
        form = self.get_form(id="main")
        form["__EVENTTARGET"] = "MM$m_PostBack"
        form["__EVENTARGUMENT"] = "CPTSYNT1"

        fix_form(form)
        form.submit()

    def go_transfer_list(self):
        form = self.get_form(id="main")

        form["__EVENTARGUMENT"] = "HISVIR0&codeMenu=WVI3"
        form["__EVENTTARGET"] = "MM$Menu_Ajax"

        fix_form(form)
        form.submit()

    @method
    class iter_transfers(TableElement):
        head_xpath = '//table[@summary="Liste des RICE à imprimer"]//th'
        item_xpath = '//table[@summary="Liste des RICE à imprimer"]//tr[td]'

        col_amount = "Montant"
        col_recipient_label = "Bénéficiaire"
        col_label = "Référence"
        col_date = "Date"

        class item(ItemElement):
            klass = Transfer

            obj_amount = CleanDecimal.French(TableCell("amount"))
            obj_recipient_label = CleanText(TableCell("recipient_label"))
            obj_label = CleanText(TableCell("label"))
            obj_date = Date(CleanText(TableCell("date")), dayfirst=True)

    def is_history_of(self, account_id):
        """
        Check whether the displayed history is for the correct account.
        If we do not find the select box we consider we are on the expected account (like it was before this check)
        """
        if self.doc.xpath('//select[@id="MM_HISTORIQUE_COMPTE_m_ExDropDownList"]'):
            return bool(self.doc.xpath('//option[@value="%s" and @selected]' % account_id))
        return True

    def go_history(self, info, is_cbtab=False):
        form = self.get_form(id="main")

        if is_cbtab:
            target = info["type"]
        else:
            target = "SYNTHESE"

        form["__EVENTTARGET"] = "MM$%s" % target
        form["__EVENTARGUMENT"] = info["link"]

        if "MM$m_CH$IsMsgInit" in form and (form["MM$m_CH$IsMsgInit"] == "0" or info["type"] == "ASSURANCE_VIE"):
            form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$SYNTHESE"

        fix_form(form)
        return form.submit()

    def go_history_netpro(
        self,
        info,
    ):
        """
        On the netpro website the go_history() does not work.
        Even from a web browser the site does not work, and display the history of the first account
        We use a different post to go through and display the history we need
        """
        form = self.get_form(id="main")
        form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$HISTORIQUE_COMPTE$m_ExDropDownList"
        form["MM$HISTORIQUE_COMPTE$m_ExDropDownList"] = info["id"]
        form["__EVENTTARGET"] = "MM$HISTORIQUE_COMPTE$m_ExDropDownList"

        fix_form(form)
        return form.submit()

    def get_form_to_detail(self, transaction):
        m = re.match(r'.*\("(.*)", "(DETAIL_OP&[\d]+).*\)\)', transaction._link)
        # go to detailcard page
        form = self.get_form(id="main")
        form["__EVENTTARGET"] = m.group(1)
        form["__EVENTARGUMENT"] = m.group(2)
        fix_form(form)
        return form

    def get_history(self):
        i = 0
        ignore = False
        for tr in self.doc.xpath('//table[@cellpadding="1"]/tr') + self.doc.xpath(
            '//tr[@class="rowClick" or @class="rowHover"]'
        ):
            tds = tr.findall("td")

            if len(tds) < 4:
                continue

            # if there are more than 4 columns, ignore the first one.
            i = min(len(tds) - 4, 1)

            if tr.attrib.get("class", "") == "DataGridHeader":
                if tds[2].text == "Titulaire":
                    ignore = True
                else:
                    ignore = False
                continue

            if ignore:
                continue

            # Remove useless details
            detail = tr.xpath('.//div[has-class("detail")]')
            if len(detail) > 0:
                detail[0].drop_tree()

            t = Transaction()

            date = "".join([txt.strip() for txt in tds[i + 0].itertext()])
            raw = " ".join([txt.strip() for txt in tds[i + 1].itertext()])
            debit = "".join([txt.strip() for txt in tds[-2].itertext()])
            credit = "".join([txt.strip() for txt in tds[-1].itertext()])

            t.parse(date, re.sub(r"[ ]+", " ", raw))

            card_debit_date = self.doc.xpath(
                '//span[@id="MM_HISTORIQUE_CB_m_TableTitle3_lblTitle"] | //label[contains(text(), "débiter le")]'
            )
            if card_debit_date:
                t.rdate = t.bdate = Date(dayfirst=True).filter(date)
                m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", card_debit_date[0].text)
                assert m
                t.date = Date(dayfirst=True).filter(m.group(1))

            if t.date and t.rdate and abs(t.date.year - t.rdate.year) > 1:
                # safety check in case we parsed a wrong rdate
                t.rdate = NotAvailable

            if t.date is NotAvailable:
                continue
            if any(pattern in t.raw.lower() for pattern in ("tot dif", "fac cb")):
                t._link = Link(tr.xpath("./td/a"))(self.doc)

            # "Cb" for new site, "CB" for old one
            mtc = re.match(r"(Cb|CB) (\d{4}\*+\d{6}) ", raw)
            if mtc is not None:
                t.card = mtc.group(2)

            t.set_amount(credit, debit)
            yield t

            i += 1

    def go_next(self):
        # <a id="MM_HISTORIQUE_CB_lnkSuivante" class="next" href="javascript:WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions(&quot;MM$HISTORIQUE_CB$lnkSuivante&quot;, &quot;&quot;, true, &quot;&quot;, &quot;&quot;, false, true))">Suivant<span class="arrow">></span></a>

        link = self.doc.xpath('//a[contains(@id, "lnkSuivante")]')
        if len(link) == 0 or "disabled" in link[0].attrib or link[0].attrib.get("class") == "aspNetDisabled":
            return False

        account_type = "COMPTE"
        m = re.search(r"HISTORIQUE_(\w+)", link[0].attrib["href"])
        if m:
            account_type = m.group(1)

        form = self.get_form(id="main")

        form["__EVENTTARGET"] = "MM$HISTORIQUE_%s$lnkSuivante" % account_type
        form["__EVENTARGUMENT"] = ""

        if "MM$m_CH$IsMsgInit" in form and form["MM$m_CH$IsMsgInit"] == "N":
            form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$HISTORIQUE_COMPTE$lnkSuivante"

        fix_form(form)
        form.submit()

        return True

    def go_life_insurance(self, account):
        # The site shows nothing about life insurance accounts except balance, links are disabled
        if "measure_id" in getattr(account, "_info", ""):
            return

        link = self.doc.xpath("//tr[td[contains(., " + account.id + ") ]]//a")[0]
        m = re.search(
            r"PostBackOptions?\([\"']([^\"']+)[\"'],\s*['\"]((REDIR_ASS_VIE)?[\d\w&]+)?['\"]",
            link.attrib.get("href", ""),
        )
        if m is not None:
            form = self.get_form(id="main")

            form["__EVENTTARGET"] = m.group(1)
            form["__EVENTARGUMENT"] = m.group(2)

            form["MM$m_CH$IsMsgInit"] = "0"
            form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$SYNTHESE"

            fix_form(form)
            form.submit()

    def transfer_link(self):
        return self.doc.xpath(
            '//a[span[contains(text(), "Effectuer un virement")]] | //a[contains(text(), "Réaliser un virement")]'
        )

    def go_transfer_via_history(self, account):
        self.go_history(account._info)

        # check that transfer is available for the connection before try to go on transfer page
        # otherwise website will continually crash
        if self.transfer_link():
            self.browser.page.go_transfer(account)

    def go_transfer_page(self):
        link = self.transfer_link()
        if len(link) == 0:
            return False
        else:
            link = link[0]
        m = re.search(r"PostBackOptions?\([\"']([^\"']+)[\"'],\s*['\"]([^\"']+)?['\"]", link.attrib.get("href", ""))
        form = self.get_form(id="main")
        if "MM$HISTORIQUE_COMPTE$btnCumul" in form:
            del form["MM$HISTORIQUE_COMPTE$btnCumul"]
        form["__EVENTTARGET"] = m.group(1)
        form["__EVENTARGUMENT"] = m.group(2)
        form.submit()

    def go_transfer(self, account):
        if self.go_transfer_page() is False:
            return self.go_transfer_via_history(account)

    def go_emitters(self):
        return self.go_transfer_page()

    def transfer_unavailable(self):
        return CleanText(
            """//li[contains(text(), "Pour accéder à cette fonctionnalité, vous devez disposer d’un moyen d’authentification renforcée")]"""
        )(self.doc)

    def loan_unavailable_msg(self):
        msg = CleanText('//span[@id="MM_LblMessagePopinError"] | //p[@id="MM_ERREUR_PAGE_BLANCHE_pAlert"]')(self.doc)
        if msg:
            return msg

    def is_subscription_unauthorized(self):
        return "non autorisée" in CleanText('//div[@id="MM_ContentMain"]')(self.doc)

    def get_email_needed_message(self):
        return CleanText('//span[contains(@id, "NonEligibleRenseignerEmail")]')(self.doc)

    def go_pro_transfer_availability(self):
        form = self.get_form(id="main")
        form["__EVENTTARGET"] = "Menu_AJAX"
        form["__EVENTARGUMENT"] = "VIRLSRM0"
        form["m_ScriptManager"] = "m_ScriptManager|Menu_AJAX"
        form.submit()

    def is_transfer_allowed(self):
        return not self.doc.xpath('//ul/li[contains(text(), "Aucun compte tiers n\'est disponible")]')

    def levies_page_enabled(self):
        """Levies page does not exist in the nav bar for every connections"""
        return CleanText('//a/span[contains(text(), "Suivre mes prélèvements reçus")]')(
            self.doc
        ) or CleanText(  # new website
            '//a[contains(text(), "Suivre les prélèvements reçus")]'
        )(
            self.doc
        )  # old website

    def get_trusted_device_url(self):
        return Regexp(
            CleanText('//script[contains(text(), "trusted-device")]'),
            r'if\("([^"]+(?:trusted-device)[^"]+)"',
            default=None,
        )(self.doc)

    def get_unavailable_2fa_message(self):
        # The message might be too long, so we retrieve only the first part.
        return CleanText(
            """//div[@class="MessageErreur"]
            //li[contains(text(), "vous devez disposer d’un moyen d’authentification renforcée")]
            /br/preceding-sibling::text()"""
        )(self.doc)


class TransactionPopupPage(LoggedPage, HTMLPage):
    def is_here(self):
        return CleanText("""//div[@class="scrollPane"]/table[//caption[contains(text(), "Détail de l'opération")]]""")(
            self.doc
        )

    def complete_label(self):
        return CleanText(
            """//div[@class="scrollPane"]/table[//caption[contains(text(), "Détail de l'opération")]]//tr[2]"""
        )(self.doc)


class NewLeviesPage(IndexPage):
    """Scrape new website 'Prélèvements' page for comings for checking accounts"""

    def is_here(self):
        return CleanText('//h2[contains(text(), "Suivez vos prélèvements reçus")]')(self.doc)

    def comings_enabled(self, account_id):
        """Check if a specific account can be selected on the general levies page"""
        return account_id in CleanText('//span[@id="MM_SYNTHESE_SDD_RECUS"]//select/option/@value')(self.doc)

    @method
    class iter_coming(TableElement):
        head_xpath = '//div[contains(@id, "ListePrelevement_0")]/table[contains(@summary, "Liste des prélèvements en attente")]//tr/th'
        item_xpath = '//div[contains(@id, "ListePrelevement_0")]/table[contains(@summary, "Liste des prélèvements en attente")]//tr[contains(@id, "trRowDetail")]'

        col_label = "Libellé/Référence"
        col_coming = "Montant"
        col_date = "Date"

        class item(ItemElement):
            klass = Transaction

            # Transaction typing will mostly not work since transaction as comings will only display the debiting organism in the label
            # Labels will bear recognizable patterns only when they move from future to past, where they will be typed by iter_history
            # when transactions change state from coming to history 'Prlv' is append to their label, this will help the backend for the matching
            obj_raw = Transaction.Raw(Format("Prlv %s", Field("label")))
            obj_label = CleanText(TableCell("label"))
            obj_amount = CleanDecimal.French(TableCell("coming"), sign=lambda x: -1)
            obj_date = Date(CleanText(TableCell("date")), dayfirst=True)

            def condition(self):
                return not CleanText(
                    """
                        //p[contains(text(), "Vous n'avez pas de prélèvement en attente d'exécution.")]
                    """
                )(self)


class OldLeviesPage(IndexPage):
    """Scrape old website 'Prélèvements' page for comings for checking accounts"""

    def is_here(self):
        return CleanText('//span[contains(text(), "Suivez vos prélèvements reçus")]')(self.doc)

    def comings_enabled(self, account_id):
        """Check if a specific account can be selected on the general levies page"""
        return account_id in CleanText('//span[@id="MM_SYNTHESE_SDD_RECUS"]//select/option/@value')(self.doc)

    @method
    class iter_coming(TableElement):
        head_xpath = """//span[contains(text(), "Prélèvements en attente d'exécution")]/ancestor::table[1]/following-sibling::table[1]//tr[contains(@class, "DataGridHeader")]//td"""
        item_xpath = """//span[contains(text(), "Prélèvements en attente d'exécution")]/ancestor::table[1]/following-sibling::table[1]//tr[contains(@class, "DataGridHeader")]//following-sibling::tr"""

        col_label = "Libellé/Référence"
        col_coming = "Montant"
        col_date = "Date"

        class item(ItemElement):
            klass = Transaction

            # Transaction typing will mostly not work since transaction as comings will only display the debiting organism in the label
            # Labels will bear recognizable patterns only when they move from future to past, where they will be typed by iter_history
            # when transactions change state from coming to history 'Prlv' is append to their label, this will help the backend for the matching
            obj_raw = Transaction.Raw(Format("Prlv %s", Field("label")))
            obj_label = CleanText(TableCell("label"))
            obj_amount = CleanDecimal.French(TableCell("coming"), sign=lambda x: -1)
            obj_date = Date(CleanText(TableCell("date")), dayfirst=True)

            def condition(self):
                return not CleanText(
                    """
                    //table[@id="MM_SYNTHESE_SDD_RECUS_rpt_dgList_0"]//td[contains(text(), "Vous n'avez pas de prélèvements")]
                """
                )(self)


class CardsPage(IndexPage):
    def is_here(self):
        return CleanText('//h3[normalize-space(text())="Mes cartes (cartes dont je suis le titulaire)"]')(self.doc)

    @method
    class iter_cards(TableElement):
        head_xpath = '//table[@class="cartes"]/tbody/tr/th'

        col_label = "Carte"
        col_number = "N°"
        col_parent = "Compte dépot associé"
        col_coming = "Encours"

        item_xpath = '//table[@class="cartes"]/tbody/tr[not(th)]'
        # There are real duplicate card but only one have incoming sum.
        ignore_duplicate = True

        class item(ItemElement):
            klass = Account

            obj_type = Account.TYPE_CARD
            obj_label = Format("%s %s", CleanText(TableCell("label")), Field("id"))
            obj_number = CleanText(TableCell("number"))
            obj_id = CleanText(TableCell("number"), replace=[("*", "X")])
            obj__parent_id = CleanText(TableCell("parent"))
            obj_balance = 0
            obj_currency = Currency(TableCell("coming"))
            obj__card_links = None

            def obj_coming(self):
                if CleanText(TableCell("coming"))(self) == "-":
                    raise SkipItem("immediate debit card?")
                return CleanDecimal.French(TableCell("coming"), sign=lambda x: -1)(self)

            def condition(self):
                immediate_str = ""
                # There are some card without any information. To exclude them, we keep only account
                # with extra "option" (ex: coming transaction link, block bank card...)
                if "Faire opposition" in CleanText("./td[5]")(self):
                    # Only deferred card have this option to see coming transaction, even when
                    # there is 0 coming (Table element have no thead for the 5th column).
                    if "Consulter mon encours carte" in CleanText("./td[5]")(self):
                        return True

                    # Card without 'Consulter mon encours carte' are immediate card. There are logged
                    # for now to make the debug easier
                    immediate_str = "[Immediate card]"

                self.logger.debug(
                    "Skip card %s (no history/coming information) %s",
                    Field("number")(self),
                    immediate_str,
                )
                return False


class CardsComingPage(IndexPage):
    def is_here(self):
        return CleanText('//h2[text()="Encours de carte à débit différé"]')(self.doc)

    @method
    class iter_cards(ListElement):
        item_xpath = '//table[contains(@class, "compte") and position() = 1]//tr[contains(@id, "MM_HISTORIQUE_CB") and position() < last()]'

        class item(ItemElement):
            klass = Account

            def obj_id(self):
                # We must handle two kinds of Regexp because the 'X' are not
                # located at the same level for sub-modules such as palatine
                card_id = Regexp(
                    CleanText(Field("label"), replace=[("*", "X")]),
                    r"(\d{4}X{6}\d{6}|\d{6}X{6}\d{4})",
                    default=NotAvailable,
                )(self)

                if Env("is_id_duplicate"):
                    # We can have multiple cards with the same card number, so now we use this regex to build our
                    # own id with the name of the concerned card user
                    # label are so inconsistent it overcomplexifies the regex to handle pronouns
                    # and a varied range of cards as well
                    name = Regexp(
                        CleanText(Field("label"), replace=[("'", " ")]),
                        r"(Visa|VISA) (?:Classic|CLASSIC|Premier|PREMIER|Infinite|INFINITE|Platinum|PLATINUM|(Gold\s)*Business) (?:Izicarte )?((?:MME|ME|Mme|MR|M|M\.|MLLE|MLE|ML|LE|DD|N)?[a-zA-Zéèî,\- .]+) \d+[*]+\d+",
                    )(self).replace(" ", "_")
                    return f"{card_id}_{name}"

                return card_id

            def obj_number(self):
                return Coalesce(
                    Regexp(CleanText(Field("label")), r"(\d{6}\*{6}\d{4})", default=NotAvailable),
                    Regexp(CleanText(Field("label")), r"(\d{4}\*{6}\d{6})", default=NotAvailable),
                )(self)

            obj_type = Account.TYPE_CARD
            obj_label = CleanText("./td[1]")
            obj_balance = Decimal(0)
            obj_coming = CleanDecimal.French("./td[2]")
            obj_currency = Currency("./td[2]")
            obj__card_links = None

    def is_id_duplicate(self):
        label = CleanText(
            '//table[contains(@class, "compte") and position() = 1]//tr[contains(@id, "MM_HISTORIQUE_CB") and position() < last()]/td[1]',
            replace=[("*", "X")],
        )(self.doc)
        ids = re.findall(r"(\d{4,6}X{6}\d{4,6})", label)
        return len(ids) != len(set(ids))

    def get_card_coming_info(self, number, info):
        # If the xpath match, that mean there are only one card
        # We have enough information in `info` to get its coming transaction
        if CleanText('//tr[@id="MM_HISTORIQUE_CB_rptMois0_ctl01_trItem"]')(self.doc):
            return info

        # If the xpath match, that mean there are at least 2 cards
        xpath = '//tr[@id="MM_HISTORIQUE_CB_rptMois0_trItem_0"]'

        # In case of multiple card, first card coming's transactions are reachable
        # with information in `info`.
        if Regexp(CleanText(xpath), r"(\d{6}\*{6}\d{4})")(self.doc) == number:
            return info

        # Some cards redirect to a checking account where we cannot found them. Since we have no details or history,
        # we return None and skip them in the browser.
        if CleanText('//a[contains(text(),"%s")]' % number)(self.doc):
            # For all cards except the first one for the same check account, we have to get info through their href info
            link = CleanText(Link('//a[contains(text(),"%s")]' % number))(self.doc)
            infos = re.match(r".*(DETAIL_OP_M\d&[^\"]+).*", link)
            info["link"] = infos.group(1)

            return info
        return None


class CardsOldWebsitePage(IndexPage):
    def is_here(self):
        return CleanText(
            """
            //span[@id="MM_m_CH_lblTitle" and contains(text(), "Historique de vos encours CB")]
        """
        )(self.doc)

    def get_account(self):
        infos = CleanText('.//span[@id="MM_HISTORIQUE_CB"]/table[position()=1]//td')(self.doc)
        result = re.search(r".*(\d{11}).*", infos)
        return result.group(1)

    def get_date(self):
        title = CleanText('//span[@id="MM_HISTORIQUE_CB_m_TableTitle3_lblTitle"]')(self.doc)
        title_date = re.match(".*le (.*) sur .*", title)
        return Date(dayfirst=True).filter(title_date.group(1))

    @method
    class iter_cards(TableElement):
        head_xpath = '//table[@id="MM_HISTORIQUE_CB_m_ExDGOpeM0"]//tr[@class="DataGridHeader"]/td'
        item_xpath = '//table[@id="MM_HISTORIQUE_CB_m_ExDGOpeM0"]//tr[not(contains(@class, "DataGridHeader")) and position() < last()]'

        col_label = "Libellé"
        col_coming = "Solde"

        class item(ItemElement):
            klass = Account

            obj_type = Account.TYPE_CARD
            obj_label = Format("%s %s", CleanText(TableCell("label")), CleanText(Field("number")))
            obj_balance = 0
            obj_coming = CleanDecimal.French(TableCell("coming"))
            obj_currency = Currency(TableCell("coming"))
            obj__card_links = None

            def obj__parent_id(self):
                return self.page.get_account()

            def obj_number(self):
                return CleanText(TableCell("number"))(self).replace("*", "X")

            def obj_id(self):
                number = Field("number")(self).replace("X", "")
                account_id = "%s-%s" % (self.obj__parent_id(), number)
                return account_id

            def obj__coming_eventargument(self):
                url = Attr(".//a", "href")(self)
                res = re.match(r'.*(DETAIL_OP_M0\&.*;\d{8})", .*', url)
                return res.group(1)

        def parse(self, obj):
            # There are no thead name for this column.
            self._cols["number"] = 3

    @method
    class iter_coming(TableElement):
        head_xpath = '//table[@id="MM_HISTORIQUE_CB_m_ExDGDetailOpe"]//tr[@class="DataGridHeader"]/td'
        item_xpath = '//table[@id="MM_HISTORIQUE_CB_m_ExDGDetailOpe"]//tr[not(contains(@class, "DataGridHeader"))]'

        col_label = "Libellé"
        col_coming = "Débit"
        col_date = "Date"

        class item(ItemElement):
            klass = Transaction

            obj_type = Transaction.TYPE_DEFERRED_CARD
            obj_label = CleanText(TableCell("label"))
            obj_amount = CleanDecimal.French(TableCell("coming"), sign=lambda x: -1)
            obj_rdate = obj_bdate = Date(CleanText(TableCell("date")), dayfirst=True)

            def obj_date(self):
                return self.page.get_date()


class ConsLoanPage(JsonPage):
    def get_conso(self):
        return self.doc


class LoadingPage(HTMLPage):
    def on_load(self):
        # CTX cookie seems to corrupt the request fetching info about "credit
        # renouvelable" and to lead to a 409 error
        if "CTX" in self.browser.session.cookies.keys():
            del self.browser.session.cookies["CTX"]

        form = self.get_form(id="REROUTAGE")
        form.submit()


class NatixisRedirectPage(LoggedPage, HTMLPage):
    def on_load(self):
        try:
            form = self.get_form(id="NaAssurance")
        except FormNotFound:
            form = self.get_form(id="formRoutage")
        form.submit()


class NatixisErrorPage(LoggedPage, HTMLPage):
    pass


class MarketPage(LoggedPage, HTMLPage):
    def is_error(self):
        return CleanText('//caption[contains(text(),"Erreur")]')(self.doc)

    def parse_decimal(self, td, percentage=False):
        value = CleanText(".")(td)
        if value and value != "-":
            if percentage:
                return Decimal(FrenchTransaction.clean_amount(value)) / 100
            return Decimal(FrenchTransaction.clean_amount(value))
        else:
            return NotAvailable

    def submit(self):
        form = self.get_form(nr=0)

        form.submit()

    def iter_investment(self):
        for tbody in self.doc.xpath('//table[@summary="Contenu du portefeuille valorisé"]/tbody'):
            inv = Investment()
            inv.label = CleanText(".")(tbody.xpath("./tr[1]/td[1]/a/span")[0])
            inv.code = CleanText(".")(tbody.xpath("./tr[1]/td[1]/a")[0]).split(" - ")[1]
            if is_isin_valid(inv.code):
                inv.code_type = Investment.CODE_TYPE_ISIN
            else:
                inv.code_type = NotAvailable
            inv.quantity = self.parse_decimal(tbody.xpath("./tr[2]/td[2]")[0])
            inv.unitvalue = self.parse_decimal(tbody.xpath("./tr[2]/td[3]")[0])
            inv.unitprice = self.parse_decimal(tbody.xpath("./tr[2]/td[5]")[0])
            inv.valuation = self.parse_decimal(tbody.xpath("./tr[2]/td[4]")[0])
            inv.diff = self.parse_decimal(tbody.xpath("./tr[2]/td[7]")[0])

            yield inv

    def get_valuation_diff(self, account):
        val = CleanText(self.doc.xpath('//td[contains(text(), "values latentes")]/following-sibling::*[1]'))
        account.valuation_diff = CleanDecimal(Regexp(val, r"([^\(\)]+)"), replace_dots=True)(self)

    def is_on_right_portfolio(self, account):
        return len(
            self.doc.xpath(
                '//form[@class="choixCompte"]//option[@selected and contains(text(), $id)]', id=account._info["id"]
            )
        )

    def get_compte(self, account):
        return self.doc.xpath("//option[contains(text(), $id)]/@value", id=account._info["id"])[0]

    def come_back(self):
        link = Link('//div/a[contains(text(), "Accueil accès client")]', default=NotAvailable)(self.doc)
        if link:
            self.browser.location(link)


class LifeInsurance(MarketPage):
    pass


class LifeInsuranceHistory(LoggedPage, JsonPage):
    def build_doc(self, text):
        # If history is empty, there is no text
        if not text:
            return {}
        return super(LifeInsuranceHistory, self).build_doc(text)

    @method
    class iter_history(DictElement):
        def find_elements(self):
            return self.el or []  # JSON contains 'null' if no transaction

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # Eliminate transactions without amount
                return Dict("montantBrut")(self)

            obj_raw = Transaction.Raw(Dict("type/libelleLong"))
            obj_amount = Eval(float_to_decimal, Dict("montantBrut/valeur"))

            def obj_date(self):
                date = Dict("dateEffet")(self)
                if date:
                    return datetime.fromtimestamp(date / 1000)
                return NotAvailable

            obj_vdate = obj_rdate = obj_date


class LifeInsuranceInvestments(LoggedPage, JsonPage):
    @method
    class iter_investment(DictElement):

        def find_elements(self):
            return self.el["repartition"]["supports"] or []  # JSON contains 'null' if no investment

        class item(ItemElement):
            klass = Investment

            # For whatever reason some labels start with a '.' (for example '.INVESTMENT')
            obj_label = CleanText(Dict("libelleSupport"), replace=[(".", "")])
            obj_valuation = Eval(float_to_decimal, Dict("montantBrutInvesti/valeur"))

            def obj_portfolio_share(self):
                invested_percentage = Dict("pourcentageInvesti", default=None)(self)
                if invested_percentage:
                    return float_to_decimal(invested_percentage) / 100
                return NotAvailable

            # Note: the following attributes are not available for euro funds
            def obj_vdate(self):
                vdate = Dict("cotation/date")(self)
                if vdate:
                    return datetime.fromtimestamp(vdate / 1000)
                return NotAvailable

            def obj_quantity(self):
                if Dict("nombreParts")(self):
                    return Eval(float_to_decimal, Dict("nombreParts"))(self)
                return NotAvailable

            def obj_diff(self):
                if Dict("montantPlusValue/valeur", default=None)(self):
                    return Eval(float_to_decimal, Dict("montantPlusValue/valeur"))(self)
                return NotAvailable

            def obj_diff_ratio(self):
                if Dict("tauxPlusValue")(self):
                    return Eval(lambda x: float_to_decimal(x) / 100, Dict("tauxPlusValue"))(self)
                return NotAvailable

            def obj_unitvalue(self):
                if Dict("cotation/montant")(self):
                    return Eval(float_to_decimal, Dict("cotation/montant/valeur"))(self)
                return NotAvailable

            obj_code = IsinCode(CleanText(Dict("codeIsin", default="")), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict("codeIsin", default="")))

    def is_contract_closed(self):
        return Dict("etatContrat/code")(self.doc) == "01"


class NatixisLIHis(LoggedPage, JsonPage):
    @method
    class get_history(DictElement):
        item_xpath = None

        class item(ItemElement):
            klass = Transaction

            obj_amount = Eval(float_to_decimal, Dict("montantNet"))
            obj_raw = CleanText(Dict("libelle", default=""))
            obj_vdate = Date(Dict("dateValeur", default=NotAvailable), default=NotAvailable)
            obj_date = Date(Dict("dateEffet", default=NotAvailable), default=NotAvailable)
            obj_investments = NotAvailable
            obj_type = Transaction.TYPE_BANK

            def validate(self, obj):
                return obj.raw and obj.date


class NatixisLIInv(LoggedPage, JsonPage):
    @method
    class get_investments(DictElement):
        item_xpath = "detailContratVie/valorisation/supports"

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict("nom"))
            obj_code = IsinCode(CleanText(Dict("codeIsin", default="")), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict("codeIsin", default="")))

            def obj_vdate(self):
                dt = Dict("dateValeurUniteCompte", default=None)(self)
                if dt is None:
                    dt = self.page.doc["detailContratVie"]["valorisation"]["date"]
                return Date().filter(dt)

            obj_valuation = Eval(float_to_decimal, Dict("montant"))
            obj_quantity = Eval(float_to_decimal, Dict("nombreUnitesCompte"))
            obj_unitvalue = Eval(float_to_decimal, Dict("valeurUniteCompte"))

            def obj_diff(self):
                diff = Dict("capitalGainView/pvLatentInEuroOrigin", default=None)(self)
                if diff is not None:
                    return float_to_decimal(diff)
                return NotAvailable

            def obj_diff_ratio(self):
                diff_ratio_percent = Dict("capitalGainView/pvLatentInPorcentOrigin", default=None)(self)
                if diff_ratio_percent is not None:
                    return float_to_decimal(diff_ratio_percent) / 100
                return NotAvailable

            def obj_portfolio_share(self):
                repartition = Dict("repartition", default=None)(self)
                if repartition:
                    return float_to_decimal(repartition) / 100
                return NotAvailable

    def has_history(self):
        """
        Uses millevie website's responses to guess if there is an history or not

        A Millevie LI doesn't necessarily have an history
        (trying to get an history will result in an error page.
        ex: Millevie PER doesn't have history, but Millevie Essentielle does)

        The request to get the history is registered as a callback of clicking on the
        history tab "Historique" on the Millevie LIs website. But this tab is not
        always generated by the client-side code, only if the peri parameter is False:

        ```
        // in etnav2-features-consultation-vie-vie-module-ngfactory.43baa1615f8de9834e0c.js:

        n.listtabs = n.listtabs = [{
            label: "Consulter",
            link: "consulter"
        }, {
            label: "Historique",
            link: "historique",
            disabled: u
        }, {
            label: "Documents",
            link: "documents",
            disabled: u
        }], a && a.peri && n.listtabs.splice(1, 1)
        ```
        """
        return not self.doc["peri"]


class MeasurePage(IndexPage):
    def is_here(self):
        return self.doc.xpath('//span[contains(text(), "Liste de vos mesures")]')


class AuthentPage(LoggedPage, HTMLPage):
    def is_here(self):
        return bool(CleanText('//h2[contains(text(), "Authentification réussie")]')(self.doc))

    def go_on(self):
        form = self.get_form(id="main")
        form["__EVENTTARGET"] = "MM$RETOUR_OK_SOL$m_ChoiceBar$lnkRight"
        form.submit()


class TransactionsDetailsPage(LoggedPage, HTMLPage):

    def is_here(self):
        return bool(
            CleanText(
                '//h2[contains(text(), "Débits différés imputés")] | //span[@id="MM_m_CH_lblTitle" and contains(text(), "Débit différé imputé")]'
            )(self.doc)
        )

    @pagination
    @method
    class get_detail(TableElement):
        item_xpath = '//table[@id="MM_ECRITURE_GLOBALE_m_ExDGEcriture"]/tr[not(@class)] | //table[has-class("small special")]//tbody/tr[@class="rowClick"]'
        head_xpath = '//table[@id="MM_ECRITURE_GLOBALE_m_ExDGEcriture"]/tr[@class="DataGridHeader"]/td | //table[has-class("small special")]//thead/tr/th'

        col_date = "Date"
        col_label = ["Opération", "Libellé"]
        col_debit = "Débit"
        col_credit = "Crédit"

        def next_page(self):
            # only for new website, don't have any accounts with enough deferred card transactions on old webiste
            if self.page.doc.xpath(
                """
                //a[contains(@id, "lnkSuivante") and not(contains(@disabled,"disabled"))
                    and not(contains(@class, "aspNetDisabled"))]
            """
            ):
                form = self.page.get_form(id="main")
                form["__EVENTTARGET"] = "MM$ECRITURE_GLOBALE$lnkSuivante"
                form["__EVENTARGUMENT"] = ""
                fix_form(form)
                return form.request
            return

        class item(ItemElement):
            klass = Transaction

            obj_raw = Transaction.Raw(TableCell("label"))
            obj_date = Date(CleanText(TableCell("date")), dayfirst=True)
            obj__debit = CleanDecimal(TableCell("debit"), replace_dots=True, default=0)
            obj__credit = CleanDecimal(TableCell("credit"), replace_dots=True, default=0)

            def obj_amount(self):
                return abs(Field("_credit")(self)) - abs(Field("_debit")(self))

    def go_form_to_summary(self):
        # return to first page
        to_history = Link(self.doc.xpath('//a[contains(text(), "Retour à l\'historique")]'))(self.doc)
        n = re.match(r".*\([\'\"](MM\$.*?)[\'\"],.*\)$", to_history)
        form = self.get_form(id="main")
        form["__EVENTTARGET"] = n.group(1)
        form.submit()

    def go_newsite_back_to_summary(self):
        form = self.get_form(id="main")
        form["__EVENTTARGET"] = "MM$ECRITURE_GLOBALE$lnkRetourHisto"
        form.submit()


class ActivationSubscriptionPage(LoggedPage, HTMLPage, NoAccountCheck):
    def is_here(self):
        return CleanText('//span[contains(text(), "En activant le format numérique")]')(self.doc)

    def send_check_no_accounts_form(self):
        form = self.get_form(id="main")

        form["__EVENTTARGET"] = "MM$Menu_Ajax"
        form["__EVENTARGUMENT"] = "ABOCPTI0&codeMenu=WPRO4"
        form["m_ScriptManager"] = "MM$m_UpdatePanel|MM$Menu_Ajax"
        fix_form(form)

        form.submit()


class UnavailablePage(LoggedPage, HTMLPage):
    # This page seems to not be a 'LoggedPage'
    # but it also is a redirection page from a 'LoggedPage'
    # when the required page is not unavailable
    # so it can also redirect to a 'LoggedPage' page
    pass


class CreditCooperatifMarketPage(LoggedPage, HTMLPage):
    # Stay logged when landing on the new Linebourse
    # (which is used by Credit Cooperatif's connections)
    # The parsing is done in linebourse.api.pages
    def is_error(self):
        return CleanText('//caption[contains(text(),"Erreur")]')(self.doc)


class TechnicalIssuePage(LoggedPage, HTMLPage):
    """During the navigation between accounts, loans and other spaces
    caissedepargne website can encounter a technical error"""

    pass
