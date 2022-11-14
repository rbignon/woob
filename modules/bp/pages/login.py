# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals, division

import re
from io import BytesIO

from woob.exceptions import BrowserUnavailable, BrowserIncorrectPassword, NoAccountsException, ActionNeeded
from woob.browser.pages import LoggedPage
from woob.browser.filters.standard import CleanText, Regexp, Lower
from woob.tools.captcha.virtkeyboard import VirtKeyboard

from .base import MyHTMLPage


class UnavailablePage(MyHTMLPage):
    def on_load(self):
        raise BrowserUnavailable()


class Keyboard(VirtKeyboard):
    symbols = {
        '0': ('daa52d75287bea58f505823ef6c8b96c', 'e5d6dc589f00e7ec3ba0e45a1fee1220', '15853efac05847bcee90f6da436a5ae8'),
        '1': ('f5da96c2592803a8cdc5a928a2e4a3b0', '9732b03ce3bdae7a44df9a7b4e092a07', '40438237b2344b5f170278026b8d0599'),
        '2': ('9ff78367d5cb89cacae475368a11e3af', '3b4387242c42bd39dbc263eac0718a49', '4fe210d72b2522ca8002c686d89d2d70'),
        '3': ('908a0a42a424b95d4d885ce91bc3d920', '14fa1e5083fa0a0c0cded72a2139921b', '31e0f2af25245463ed1129ec09132d62'),
        '4': ('3fc069f33b801b3d0cdce6655a65c0ac', '72792dbef888f1176f1974c86a94a084', '072b6a9b2394e9b3326856c078cbf7f9'),
        '5': ('58a2afebf1551d45ccad79fad1600fc3', '1e9ddf1e5a12ebaeaea26cca6f752a87', 'edca189f37134ca0073cfeb85bad8af6'),
        '6': ('7fedfd9e57007f2985c3a1f44fb38ea1', '4e3a917198e89a2c16b9379f9a33f2a1', '4f550990aee90cf1424031c4dba10193'),
        '7': ('389b8ef432ae996ac0141a2fcc7b540f', '33b90787a8014667b2acd5493e5641d2', '9d17f6613c551f584b8422bf78bec9a4'),
        '8': ('bf357ff09cc29ea544991642cd97d453', 'e4b30e90bbc2c26c2893120c8adc9d64', '3f4c078bcdab5d13eb6d16fefc9ced0c'),
        '9': ('b744015eb89c1b950e13a81364112cd6', 'b400c35438960de101233b9c846cd5eb', '895388bef2764006dfffa3c1439811de'),
    }

    color = (0xff, 0xff, 0xff)

    def __init__(self, page):
        img_url = (
            Regexp(CleanText('//style'), r'background:url\((.*?)\)', default=None)(page.doc)
            or Regexp(CleanText('//script'), r'IMG_ALL = "(.*?)"', default=None)(page.doc)
        )

        size = 252
        if not img_url:
            img_url = page.doc.xpath('//img[@id="imageCVS"]')[0].attrib['src']
            size = 146

        coords = {}

        x, y, width, height = (0, 0, size // 4, size // 4)
        for i, _ in enumerate(page.doc.xpath('//div[@id="imageclavier"]//button')):
            code = '%02d' % i
            coords[code] = (x + 4, y + 4, x + width - 8, y + height - 8)
            if (x + width + 1) >= size:
                y += height + 1
                x = 0
            else:
                x += width + 1

        data = page.browser.open(img_url).content
        VirtKeyboard.__init__(self, BytesIO(data), coords, self.color)

        self.check_symbols(self.symbols, page.browser.responses_dirname)

    def get_symbol_code(self, md5sum):
        code = VirtKeyboard.get_symbol_code(self, md5sum)
        return '%02d' % int(code.split('_')[-1])

    def get_string_code(self, string):
        code = ''
        for c in string:
            code += self.get_symbol_code(self.symbols[c])
        return code

    def get_symbol_coords(self, coords):
        # strip borders
        x1, y1, x2, y2 = coords
        return VirtKeyboard.get_symbol_coords(self, (x1 + 3, y1 + 3, x2 - 3, y2 - 3))


class LoginPage(MyHTMLPage):
    def login(self, login, pwd):
        vk = Keyboard(self)

        form = self.get_form(name='formAccesCompte')
        form['password'] = vk.get_string_code(pwd)
        form['username'] = login
        form.submit()


class repositionnerCheminCourant(LoggedPage, MyHTMLPage):
    def on_load(self):
        super(repositionnerCheminCourant, self).on_load()
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
        if self.doc.xpath("""//span[contains(text(), "L'identifiant utilisé est celui d'une Entreprise ou d'une Association")]"""):
            raise BrowserIncorrectPassword("L'identifiant utilisé est celui d'une Entreprise ou d'une Association")
        no_accounts = CleanText('//div[@class="textFCK"]')(self.doc)
        if no_accounts:
            raise NoAccountsException(no_accounts)
        MyHTMLPage.on_load(self)


class CheckPassword(LoggedPage, MyHTMLPage):
    def on_load(self):
        MyHTMLPage.on_load(self)
        self.browser.location("https://voscomptesenligne.labanquepostale.fr/voscomptes/canalXHTML/comptesCommun/synthese_assurancesEtComptes/init-synthese.ea")


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
        status_message = CleanText('//div[@class="textFCK"]')(self.doc)
        if re.search(
                'avez pas de solution d’authentification forte'
                + '|une authentification forte est désormais nécessaire'
                + "|avez pas encore activé votre service gratuit d'authentification forte"
                + '|Cette validation vous sera ensuite demandée tous les 90 jours',
                status_message
        ):
            return 'no2fa'
        elif re.search(
                'Une authentification forte via Certicode Plus vous'
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


class Validated2FAPage(MyHTMLPage):
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
