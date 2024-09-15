# Copyright(C) 2010-2011 Nicolas Duhamel
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

from woob.browser.filters.standard import CleanText, Lower, Regexp
from woob.browser.pages import HTMLPage, LoggedPage, JsonPage
from woob.exceptions import (
    ActionNeeded, ActionType, BrowserIncorrectPassword,
    BrowserUnavailable, ParseError,
)
from woob.capabilities.bank import NoAccountsException

from .base import MyHTMLPage


class UnavailablePage(MyHTMLPage):
    def on_load(self):
        raise BrowserUnavailable()


class LoginPage(MyHTMLPage):
    def login(self, login, pwd):
        # we need to get iscd data from js file to complete the login form.
        dasti_js = self.browser.open('https://d21j9nkdg2p3wo.cloudfront.net/321226/dasti.js').text
        iscd = re.match(r'.*j=\"(\w{52})\".*', dasti_js).group(1)

        form = self.get_form(name='formAccesCompte')
        form['password'] = self.get_password_from_virtualkeyboard(pwd)
        form['username'] = login
        form['iscdName'] = iscd
        form['cltName'] = '1'
        form.submit()

    def get_password_from_virtualkeyboard(self, password):
        # Virtual keyboard is composed of buttons filled randomly with numbers from 0 to 9,
        # each digit of the password is replaced by the index of the corresponding button.
        vk = {}
        buttons = CleanText('//div[@data-tb-cvd-id="password"]/div/button/text()')(self.doc)

        for index, elt in enumerate(buttons.replace(' ', '')):
            vk[elt] = str(index)

        code = ''
        for number in password:
            code += vk[number]

        return code


class PostLoginPage(HTMLPage):
    def get_error_message(self):
        # This error is contained in a very simple HTML page,
        # inside a font tag, child of an h1 tag.
        return CleanText('//h2[@id="title"]')(self.doc)


class LienJavascript(HTMLPage):

    def is_here(self):
        try:
            Regexp(
                CleanText('//html/head/script[@type="text/javascript"]'),
                r'^top.location.replace\(..*.\);$')(self.doc)
            return True
        except ParseError:
            return False

    def on_load(self):
        if self.is_here():
            url = Regexp(
                CleanText('//script[@type="text/javascript"]'),
                r'top.location.replace\(.(.*).\)')(self.doc)
            self.browser.location(url)


class repositionnerCheminCourant(LoggedPage, MyHTMLPage):
    is_here = True

    def on_load(self):
        super().on_load()
        response = self.browser.open("https://voscomptesenligne.labanquepostale.fr/voscomptes/canalXHTML/securite/authentification/initialiser-identif.ea")
        if isinstance(response.page, Initident):
            response.page.on_load()
        if "vous ne disposez pas" in response.text:
            raise BrowserIncorrectPassword("No online banking service for these ids")
        if 'invitons à renouveler votre opération ultérieurement' in response.text:
            raise BrowserUnavailable()


class PersonalLoanRoutagePage(LoggedPage, MyHTMLPage):
    def form_submit(self):
        form = self.get_form()
        form.submit()


class Initident(LoggedPage, MyHTMLPage):
    def on_load(self):
        message = CleanText(
            """//p[contains(text(), "L'identifiant utilisé est celui d'une Entreprise ou d'une Association")]"""
        )(self.doc)
        if message:
            raise BrowserIncorrectPassword(message, bad_fields=['website'])
        no_accounts = CleanText('//div[@class="textFCK"]')(self.doc)
        if no_accounts:
            raise NoAccountsException(no_accounts)
        MyHTMLPage.on_load(self)


class CheckPassword(LoggedPage, MyHTMLPage):
    is_here = True

    def on_load(self):
        MyHTMLPage.on_load(self)
        self.browser.location("https://voscomptesenligne.labanquepostale.fr/voscomptes/canalXHTML/securite/authentification/retourDSP2-identif.ea")


class BadLoginPage(MyHTMLPage):
    pass


class AccountDesactivate(LoggedPage, MyHTMLPage):
    pass


class TwoFAPage(MyHTMLPage):
    def on_load(self):
        # For pro browser this page can provoke a disconnection
        # We have to do login again without 2fa
        deconnexion = self.doc.xpath('//iframe[contains(@id, "deconnexion")] | //p[@class="txt" and contains(text(), "Session expir")]')
        if deconnexion:
            self.browser.login_without_2fa()

    def get_auth_method(self):

        status_message = CleanText('//div[contains(@id, "DSP2_A2G_connexion_haut")]')(self.doc)

        if re.search(
                'avez pas de solution d’authentification forte'
                + '|une authentification forte est désormais nécessaire'
                + "|avez pas encore activé votre service gratuit d'authentification forte"
                + '|Cette validation vous sera ensuite demandée tous les 90 jours'
                + '|authentification forte n’a pas encore été activée',
                status_message
        ):
            return 'no2fa'
        elif re.search(
                'Une authentification forte via Certicode Plus vous'
                + '|Cette étape supplémentaire est obligatoire pour accéder à votre Espace Client Internet.'
                + '|vous rendre sur l’application mobile La Banque Postale',
                status_message
        ):
            return 'cer+'
        elif re.search(
                'authentification forte via Certicode vous'
                + '|code de sécurité que vous recevrez par SMS',
                status_message
        ):
            return 'cer'
        elif (
            'Nous rencontrons un problème pour valider votre opération. Veuillez reessayer plus tard'
            in status_message
        ):
            raise BrowserUnavailable(status_message)
        elif (
            "bloqué si vous n'avez pas de solution d'authentification forte"
            in status_message.lower()
        ):
            # Pour plus de sécurité, l'accès à votre Espace client Internet requiert une authentification forte tous les 90 jours,
            # En application de la Directive Européenne sur les Services de Paiement (DSP2).
            # Cette étape supplémentaire est obligatoire pour accéder à votre Espace client Internet.
            # Dès le 25 avril 2022, l'accès à votre Espace client sera bloqué si vous n'avez pas de solution d'authentification forte
            raise ActionNeeded(status_message)
        elif "authentification forte n'a pas encore été activée" in status_message.lower():
            # Vous ne pouvez pas accéder aux fonctionnalités de votre Espace client car l'authentification forte
            # n'a pas encore été activée. Pour plus de sécurité, l'accès à votre Espace client Internet requiert
            # une authentification forte à réaliser tous les 90 jours, en application de la Directive européenne
            # sur les Services de Paiement (DSP2). etc...
            short_message = CleanText('(//div[@class="textFCK"])[1]//p[1]')(self.doc)
            if short_message:
                # short_message is the first sentence only
                raise ActionNeeded(short_message, locale='fr-FR', action_type=ActionType.ENABLE_MFA)
            # just in case the short message is not present
            raise ActionNeeded(status_message, locale='fr-FR', action_type=ActionType.ENABLE_MFA)
        elif (
            'votre Espace Client Internet requiert une authentification forte tous les 90 jours'
            in status_message
        ):
            # short_message takes only the first sentence of status_message to avoid
            # some verbose explanations about how to set the SCA
            short_message = CleanText('(//div[@class="textFCK"])[1]//p[1]')(self.doc)
            if short_message:
                raise ActionNeeded(
                    "Une authentification forte est requise sur votre espace client : %s" % short_message
                )
            else:
                # raise an error to avoid silencing other no2fa/2fa messages
                raise AssertionError("New 2FA case to trigger")
        raise AssertionError('Unhandled login message: "%s"' % status_message)


class Polling2FA(JsonPage):
    pass


class Validated2FAPage(MyHTMLPage):
    is_here = True
    pass


class SmsPage(MyHTMLPage):
    def check_if_is_blocked(self):
        error_message = CleanText('//div[@class="textFCK"]')(self.doc)
        if "l'accès à votre Espace client est bloqué" in error_message:
            raise ActionNeeded(error_message)

    def get_sms_form(self):
        return self.get_form()

    def is_sms_wrong(self):
        return (
            'Le code de sécurité que vous avez saisi est erroné'
            in CleanText('//div[@id="DSP2_Certicode_AF_ErreurCode1"]//div[@class="textFCK"]')(self.doc)
        )


class DecoupledPage(MyHTMLPage):
    def get_decoupled_message(self):
        return CleanText('//div[@class="textFCK"]/p[contains(text(), "Validez votre authentification")]')(self.doc)


class NoTerminalPage(MyHTMLPage):
    def has_no_terminal(self):
        return 'aucun terminal trouve' in Lower('//span[@id="deviceSelected"]', transliterate=True)(self.doc)
