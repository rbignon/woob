# -*- coding: utf-8 -*-

# Copyright(C) 2013 Romain Bignon
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

from __future__ import absolute_import, unicode_literals

import re
from time import sleep

from woob.browser import LoginBrowser, URL, need_login, StatesMixin
from woob.exceptions import (
    BrowserIncorrectPassword, RecaptchaV2Question, BrowserUnavailable,
    ActionNeeded, AuthMethodNotImplemented, BrowserUserBanned, ActionType,
)
from woob.capabilities.bank import Account

from .pages import (
    LoginPage, MaintenancePage, HomePage, IncapsulaResourcePage, LoanHistoryPage, CardHistoryPage,
    SavingHistoryPage, LifeHistoryInvestmentsPage, CardHistoryJsonPage,
)


__all__ = ['CarrefourBanqueBrowser']


class CarrefourBanqueBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.carrefour-banque.fr'

    login = URL('/espace-client/connexion$', LoginPage)
    maintenance = URL('/maintenance', MaintenancePage)
    incapsula_ressource = URL('/_Incapsula_Resource', IncapsulaResourcePage)
    home = URL('/espace-client$', HomePage)

    loan_history = URL(r'/espace-client/pret-personnel/situation\?(.*)', LoanHistoryPage)
    saving_history = URL(
        r'/espace-client/compte-livret/solde-dernieres-operations\?(.*)',
        r'/espace-client/epargne-(libre|pass)/historique-des-operations\?(.*)',
        r'/espace-client/epargne-(libre|pass)/solde-dernieres-operations\?(.*)',
        SavingHistoryPage
    )

    card_history = URL(r'/espace-client/carte-credit/solde-dernieres-operations\?(.*)', CardHistoryPage)
    card_history_json = URL(r'/espace-client/carte-credit/consultation_solde_ajax', CardHistoryJsonPage)
    life_history_investments = URL(
        r'/espace-client/assurance-vie/solde-dernieres-operations\?(.*)',
        LifeHistoryInvestmentsPage
    )

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(CarrefourBanqueBrowser, self).__init__(*args, **kwargs)

    def locate_browser(self, state):
        self.login.go()  # Redirects to HomePage if we are logged in
        if self.home.is_here():
            # This is a necessary verification, as accessing some urls won't raise a ClientError
            # when we're not logged in.
            super(CarrefourBanqueBrowser, self).locate_browser(state)  # needed to make blackbox work

    def do_login(self):
        """
        Attempt to log in.
        Note: this method does nothing if we are already logged in.
        """
        assert isinstance(self.username, str)
        assert isinstance(self.password, str)

        if self.config['captcha_response'].get():
            data = {'g-recaptcha-response': self.config['captcha_response'].get()}
            self.incapsula_ressource.go(params={'SWCGHOEL': 'v2'}, data=data)

        self.login.go()
        # remove 2 cookies that make next request fail with a 400 if not removed
        # cookie name can change depend on ip, but seems to be constant on same ip
        # example:
        #     1st cookie        2nd cookie
        # ___utmvafIuFLPmB, ___utmvbfIuFLPmB
        # ___utmvaYauFLPmB, ___utmvbYauFLPmB
        # it may have other names...
        for cookie in self.session.cookies:
            if '___utmva' in cookie.name or '___utmvb' in cookie.name:
                # ___utmva... contains an ugly \x01
                # ___utmvb... contains an ugly \n
                self.session.cookies.pop(cookie.name)

        if self.incapsula_ressource.is_here():
            if self.page.is_javascript:
                # wait several seconds and we'll get a recaptcha instead of obfuscated javascript code,
                # (which is simpler to resolve)
                sleep(5)
                self.login.go()

            if not self.page.is_javascript:
                # cookie session is not available
                website_key = self.page.get_recaptcha_site_key()
                website_url = self.login.build()
                raise RecaptchaV2Question(website_key=website_key, website_url=website_url)
            else:
                # we got javascript page again, this shouldn't happen
                raise AssertionError("obfuscated javascript not managed")

        if self.maintenance.is_here():
            raise BrowserUnavailable(self.page.get_message())

        self.page.enter_login(self.username)
        msg = self.page.get_message_if_old_login()
        if msg:
            # carrefourbanque has changed login of their user, they have to use their new internet id
            raise BrowserIncorrectPassword(msg)

        self.page.enter_password(self.password)

        location = self.response.headers.get('Location', '')
        if 'connexion/sms' in location:
            # Detecting SCA before redirecting to avoid sending unnecessary/unhandled sms
            # Waiting for PSU contact to be able to implement SMS auth
            raise AuthMethodNotImplemented("L'authentification forte par SMS n'est pas prise en charge.")
        if location:
            # Location if redirection to Homepage or SMSPage
            # No location otherwise. eg App-val pop-in appears, other Dsp2 auth message, error message like below, etc.
            self.location(location)

        if self.login.is_here():
            error = self.page.get_error_message()
            # Sometimes some connections aren't able to login because of a
            # maintenance randomly occuring.
            if error:
                if 'travaux de maintenance dans votre Espace Client.' in error:
                    raise BrowserUnavailable(error)
                # We raise an ActionNeeded because you might have to contact your bank in this case
                if "votre compte ne vous permet pas d'accéder à votre Espace Client" in error:
                    raise ActionNeeded(error.replace('× ', ''))
                elif "saisies ne correspondent pas à l'identifiant" in error:
                    raise BrowserIncorrectPassword(error)
                elif "ce compte a été bloqué pendant 24h" in error:
                    raise BrowserUserBanned(error.replace('× ', ''))
                raise AssertionError('Unexpected error at login: "%s"' % error)

            dsp2_auth_code = self.page.get_dsp2_auth_code()
            # The dsp2 authentication code gives informations on which strong authentication
            # method is used by the user (Clé Secure: in-app validation or otp by SMS)
            # on blocked access to the account and unavailability of the service.
            if dsp2_auth_code:
                if dsp2_auth_code == 'authent_cc':
                    raise ActionNeeded(
                        "Authentifiez-vous depuis l'appli Carrefour Banque avec Clé Secure."
                    )
                elif dsp2_auth_code == 'enrolement_selection':
                    # On the website 'enrolement_selection' code corresponds to a pop-in in which the Clé Secure
                    # authentication method is advertised. The user is presented with instructions on how
                    # to install Clé Secure and he is also given the option to log in using otp by SMS.
                    raise ActionNeeded(
                        locale="fr-FR",
                        message="Veuillez choisir une méthode d'authentification forte sur votre espace personnel",
                        action_type=ActionType.ENABLE_MFA,
                    )
                elif dsp2_auth_code == 'cle_secure_locked':
                    raise ActionNeeded(
                        "A la suite de 3 tentatives d'authentification erronées, votre Clé Secure a été bloquée."
                        + ' Par mesure de sécurité, créez un nouveau code Clé Secure depuis votre appli Carrefour Banque.'
                    )
                elif dsp2_auth_code == 'service_indisponible':
                    raise BrowserUnavailable(
                        'Le service est momentanément indisponible. Excusez-nous pour la gêne occasionnée.'
                        + ' Veuillez ré-essayer ultérieurement.'
                    )
                elif 'acces_bloque' in dsp2_auth_code:
                    raise ActionNeeded(
                        "L'accès à votre Espace Client a été bloqué pour des raisons de sécurité."
                        + ' Pour le débloquer, contactez le service client de Carrefour Banque.'
                    )
                else:
                    raise AssertionError('Unhandled dsp2 authentication code at login %s' % dsp2_auth_code)

            raise AssertionError('Unexpected error at login')

    @need_login
    def get_account_list(self):
        self.home.stay_or_go()
        cards = list(self.page.iter_card_accounts())
        life_insurances = list(self.page.iter_life_accounts())
        savings = list(self.page.iter_saving_accounts())
        loans = list(self.page.iter_loan_accounts())
        return cards + life_insurances + savings + loans

    @need_login
    def iter_investment(self, account):
        if account.type != Account.TYPE_LIFE_INSURANCE:
            raise NotImplementedError()

        self.home.stay_or_go()
        self.location(account._life_investments)
        assert self.life_history_investments.is_here()
        return self.page.get_investment(account)

    @need_login
    def iter_history(self, account):
        self.home.stay_or_go()
        self.location(account.url)

        if account.type == Account.TYPE_SAVINGS:
            assert self.saving_history.is_here()
        elif account.type == Account.TYPE_CARD:
            assert self.card_history.is_here()

            card_index = re.search(r'[?&]index=(\d+)', account.url).group(1)

            previous_date = self.page.get_previous_date()
            # the website stores the transactions over more or less 1 year
            # the transactions are displayed 40 by 40 in a dynamic table
            # if there are still transactions to display but less than 40
            # they will not be display in the html
            # but they can be recovered the json API
            # to do so, we need to build a request with a dateRecup parameter
            # but because the dateRecup can't be recovered in the html (in the button to display more transactions)
            # we need to do a call to recover the timestampOperation of the last transaction sent by the api
            if not previous_date:
                # if we do the call without sending a dateRecup it will return the 40 first transactions twice
                # it will also do with a random timestamp
                # in this particular case dateRecup can be any value as long as it's not an empty string or a timestamp
                self.card_history_json.go(data={'dateRecup': 'needToNotBeEmpty', 'index': card_index})
                previous_date = self.page.get_last_timestamp()

            if previous_date:
                tr = None
                total = 0
                loop_limit = 500
                for _ in range(loop_limit):
                    self.card_history_json.go(data={'dateRecup': previous_date, 'index': card_index})
                    previous_date = self.page.get_previous_date()

                    it = iter(self.page.iter_history())
                    for _ in range(total):
                        # those transactions were returned on previous pages
                        next(it)

                    for tr in it:
                        total += 1
                        yield tr

                    if not previous_date:
                        # last page
                        if tr and tr.date:
                            self.logger.info("last transaction date %s", tr.date)
                        self.logger.info("woob scraped %s transactions", total)
                        self.logger.info("There is no previous_date in the response of the last request")
                        return
                else:
                    self.logger.info(
                        "End of loop after %s iterations but still got a next page, it will miss some transactions",
                        loop_limit
                    )
                    return

        elif account.type == Account.TYPE_LOAN:
            assert self.loan_history.is_here()
        elif account.type == Account.TYPE_LIFE_INSURANCE:
            assert self.life_history_investments.is_here()
        else:
            raise NotImplementedError()
        for tr in self.page.iter_history(account):
            yield tr
