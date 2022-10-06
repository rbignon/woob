# -*- coding: utf-8 -*-

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

from woob.browser import LoginBrowser, URL, need_login
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserPasswordExpired, ActionNeeded, ActionType,
    BrowserUnavailable,
)
from woob.capabilities.bank import Account
from woob.tools.decorators import retry
from woob.tools.json import json
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import (
    LoginPage, LoginConfirmPage, ProfilePage,
    AccountsPage, IbanPage, HistoryPage, InvestmentsPage,
    RgpdPage, IndexPage, ErrorPage, BypassAlertPage,
)


class CreditDuNordBrowser(LoginBrowser):
    ENCODING = 'UTF-8'
    BASEURL = "https://www.credit-du-nord.fr/"

    index = URL(
        '/icd/zdb/index.html',
        IndexPage
    )
    login = URL(
        r'$',
        r'/.*\?.*_pageLabel=page_erreur_connexion',
        r'/.*\?.*_pageLabel=reinitialisation_mot_de_passe',
        LoginPage
    )
    logout = URL(r'/pkmslogout')
    login_confirm = URL(r'/sec/vk/authent.json', LoginConfirmPage)

    bypass_rgpd = URL(r'/icd/zcd/data/gdpr-get-out-zs-client.json', RgpdPage)
    bypass_alert = URL(r'/icd/zcm_alerting/data/pull-events/zcm-alerting-get-out-zs-client.json', BypassAlertPage)

    error_page = URL(r'/icd/static/acces-simplifie.html', ErrorPage)

    profile = URL(r'/icd/zco/data/public-user.json', ProfilePage)
    accounts = URL(r'/icd/fdo/data/comptesExternes.json', AccountsPage)
    history = URL(r'/icd/fdo/data/detailDunCompte.json', HistoryPage)
    investments = URL(r'/icd/fdo/data/getAccountWithAsset.json', InvestmentsPage)

    iban = URL(r'/icd/zvo/data/saisieVirement/saisieVirement.json', IbanPage)

    def __init__(self, *args, **kwargs):
        self.woob = kwargs['woob']
        super(CreditDuNordBrowser, self).__init__(*args, **kwargs)

    def do_login(self):
        self.login.go()

        if self.error_page.is_here():
            msg = self.page.get_error_msg()
            if 'Suite à une erreur technique' in msg:
                raise BrowserUnavailable(msg)
            raise AssertionError('Unhandled error message: %s' % msg)

        website_unavailable = self.page.get_website_unavailable_message()
        if website_unavailable:
            raise BrowserUnavailable(website_unavailable)

        # Some users are still using their old password, that leads to a virtual keyboard crash.
        if not self.password.isdigit() or len(self.password) != 6:
            raise BrowserIncorrectPassword('Veuillez utiliser le nouveau code confidentiel fourni par votre banque.')

        self.page.login(self.username, self.password)

        assert self.login_confirm.is_here(), 'Should be on login confirmation page'

        reason = self.page.get_reason()
        status = self.page.get_status()

        if reason == 'echec_authent':
            raise BrowserIncorrectPassword()
        elif reason == 'chgt_mdp_oblig':
            # There is no message in the json return. There is just the code.
            raise BrowserPasswordExpired('Changement de mot de passe requis.')
        elif reason == 'SCA':
            raise ActionNeeded(
                locale="fr-FR", message="Vous devez réaliser la double authentification sur le portail internet",
                action_type=ActionType.PERFORM_MFA,
            )
        elif reason == 'SCAW':
            # SCAW reason was used to asked to the user to activate his 2FA, but now creditdunord also use it
            # to propose to the user to redo earlier the expiring 2FA. A later check is done (in AccountsPage)
            # in case SCAW reason is sent back for the purpose of asking 2FA to be activated.
            self.index.go()
            # This cookie is mandatory, otherwise we could encounter the "redo 2fa earlier proposal" later on the website
            # It is set through JS on CDN website
            self.session.cookies.set('SCAW', 'true', domain='www.credit-du-nord.fr')
            self.page.skip_redo_2fa()
            self.logger.warning("Skipping redo 2FA earlier proposal")
        elif reason == 'acces_bloq':
            if self.page.is_pro_space():
                raise BrowserPasswordExpired(
                    locale='fr-FR',
                    message='Suite à une erreur de saisie, vos accès aux services Mobile et Internet ont été bloqués.'
                    + " Veuillez contacter votre conseiller ou l'assistance téléphonique de Crédit du Nord.",
                )
            raise BrowserPasswordExpired(
                locale='fr-FR',
                message='Suite à une erreur de saisie, vos accès aux services Mobile et Internet ont été bloqués.'
                + ' Veuillez réinitialiser votre mot de passe sur votre espace.',
            )
        elif status != 'OK' and reason:
            raise AssertionError(f"Unhandled reason at login: {reason}")

    def do_logout(self):
        self.logout.go()
        self.session.cookies.clear()

    @retry(json.JSONDecodeError)
    def go_on_accounts(self):
        """creditdunord api sometimes return truncated JSON
        which will make the module crash. Retrying once
        seems to do the job.
        """
        self.accounts.go()

    @need_login
    def iter_accounts(self):
        can_access_accounts = False
        previous_reasons = []

        while not can_access_accounts:
            try:
                self.go_on_accounts()
                can_access_accounts = True
            except ActionNeeded as e:
                reason = str(e)

                # If first try to bypass failed, safely raise the exception
                if reason in previous_reasons:
                    raise

                # When retrieving labels page,
                # If GDPR was accepted partially the website throws a page that we treat
                # as an ActionNeeded. Sometime we can by-pass it. Hence this fix
                if reason == 'GDPR':
                    self.bypass_rgpd.go()

                # This error code can represent an alert asking the user to fill-in their e-mail,
                # which we can bypass. It can however also appear for other reasons that we cannot
                # bypass, in which case an ActionNeeded will be raised on the next iteration of the loop.
                elif reason == 'Mise à jour de votre dossier':
                    self.bypass_alert.go()

                # If the reason is not one that can be bypassed, we can immediately raise
                else:
                    raise

                previous_reasons.append(reason)

        current_bank = self.page.get_current_bank()

        accounts = list(self.page.iter_accounts(current_bank=current_bank))
        accounts.extend(self.page.iter_loans(current_bank=current_bank))

        self.iban.go(data={
            'virementType': 'INDIVIDUEL',
            'hashFromCookieMultibanque': '',
        })

        for account in accounts:
            if account.type == Account.TYPE_CARD:
                # Match the card with its checking account using the account number
                account.parent = next(
                    (account_ for account_ in accounts if (
                        account_.type == Account.TYPE_CHECKING
                        and account_.number[:-5] == account.number[:-5]
                    )),
                    None,
                )
            if (
                account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS)
                and self.page.get_status() == 'OK'  # IbanPage is not available if transfers are not authorized
            ):
                account.iban = self.page.get_iban_from_account_number(account.number)

        return accounts

    @retry(json.JSONDecodeError)
    def go_on_history(self, account_id, current_page):
        """creditdunord api sometimes return truncated JSON
        which will make the module crash. Retrying once
        seems to do the job.
        """
        self.history.go(data={
            'an200_idCompte': account_id,
            'an200_pageCourante': current_page,
        })

    @need_login
    def iter_history(self, account, coming=False):
        if coming and account.type != Account.TYPE_CARD:
            return

        current_page = 1
        has_transactions = True
        while has_transactions and current_page <= 50:
            self.go_on_history(account._custom_id, str(current_page))
            self.page.check_reason()

            if account._has_investments:
                history = self.page.iter_wealth_history()
            else:
                history = self.page.iter_history(account_type=account.type)

            for transaction in sorted_transactions(history):
                yield transaction

            has_transactions = self.page.has_transactions(account._has_investments)
            current_page = current_page + 1

    @need_login
    def iter_investment(self, account):
        if account._has_investments:
            self.investments.go(data={'an200_bankAccountId': account._custom_id})
            if self.page.has_investments():
                for investment in self.page.iter_investment():
                    yield investment
            else:
                yield create_french_liquidity(account.balance)

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
