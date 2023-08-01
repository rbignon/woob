# Copyright(C) 2019 Powens
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
from datetime import date
from time import time

from dateutil.relativedelta import relativedelta

from woob.browser import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.exceptions import (
    ActionNeeded, ActionType, BrowserIncorrectPassword,
    BrowserPasswordExpired, BrowserUnavailable, BrowserUserBanned,
    OTPSentType, SentOTPQuestion,
)
from woob.tools.capabilities.bill.documents import merge_iterators

from .pages import (
    CguPage, CtPage, DocumentsDetailsPage, DocumentsFirstSummaryPage, DocumentsLastSummaryPage,
    ErrorPage, LoginPage, NewPasswordPage, RedirectPage, SubscriptionPage,
    AmeliConnectOpenIdPage, LoginContinuePage,
)


class AmeliBrowser(TwoFactorBrowser):
    BASEURL = 'https://assure.ameli.fr'
    HAS_CREDENTIALS_ONLY = True

    error_page = URL(r'/vu/INDISPO_COMPTE_ASSURES.html', ErrorPage)
    login_page = URL(
        r'/PortailAS/appmanager/PortailAS/assure\?_nfpb=true&connexioncompte_2actionEvt=afficher.*',
        r'/PortailAS/appmanager/PortailAS/assure\?_nfpb=true&.*validationconnexioncompte.*',
        LoginPage
    )
    # This login_continue_page is only needed in some cases where an action needed is going
    # to be triggered. Since the website does not do any redirection at this point we must
    #  look into the HTML of this page to know if there's going to be an action needed.
    login_continue_page = URL(
        r'/PortailAS/appmanager/PortailAS/assure\?_nfpb=true&_pageLabel=as_login_page&connexioncompte_2actionEvt=connecter',
        LoginContinuePage,
    )
    new_password_page = URL(
        r'/PortailAS/appmanager/PortailAS/assure\?.*as_modif_code_perso_ameli_apres_reinit_page',
        NewPasswordPage
    )
    redirect_page = URL(
        r'/PortailAS/appmanager/PortailAS/assure\?_nfpb=true&.*validationconnexioncompte.*',
        RedirectPage
    )
    cgu_page = URL(
        r'/PortailAS/appmanager/PortailAS/assure\?_nfpb=true&_pageLabel=as_conditions_generales_page.*',
        CguPage
    )
    subscription_page = URL(
        r'/PortailAS/appmanager/PortailAS/assure\?_nfpb=true&_pageLabel=as_info_perso_page',
        SubscriptionPage
    )
    documents_details_page = URL(r'/PortailAS/paiements.do', DocumentsDetailsPage)
    documents_first_summary_page = URL(
        r'PortailAS/appmanager/PortailAS/assure\?_nfpb=true&_pageLabel=as_releve_mensuel_paiement_page',
        DocumentsFirstSummaryPage
    )
    documents_last_summary_page = URL(
        r'PortailAS/portlets/relevemensuelpaiement/relevemensuelpaiement.do\?actionEvt=afficherPlusReleves',
        DocumentsLastSummaryPage
    )
    ct_page = URL(r'/PortailAS/JavaScriptServlet', CtPage)
    ameliconnect_openid = URL(
        r'https://ameliconnect.ameli.fr/oauth2/authorize\?.*',
        r'https://ameliconnect.ameli.fr/oauth2/authorize\?scope=openid+ameliconnect&response_type=code&nonce=.*&redirect_uri=.*&state=.*&client_id=compte_AS',
        AmeliConnectOpenIdPage
    )

    # Should last 6 month on trusted devices
    TWOFA_DURATION = 180 * 24 * 60
    # The mail says that the OTP code is valid for 15 minutes
    STATE_DURATION = 15
    __states__ = ('otp_form_data', 'otp_form_url', 'trust_connect')

    def __init__(self, config, *args, **kwargs):
        super(AmeliBrowser, self).__init__(config, *args, **kwargs)
        self.login_source = config['login_source'].get()
        self.otp_email = config['otp_email'].get()
        self.otp_form_data = None
        self.otp_form_url = None
        self.trust_connect = None  # Cookie linked to the trusted device

        self.AUTHENTICATION_METHODS = {
            'otp_email': self.handle_otp,
        }

    def init_login(self):
        """
        Method to implement initiation of login on website.

        This method should raise an exception.

        SCA exceptions :
        - AppValidation for polling method
        - BrowserQuestion for SMS method, token method etc.

        Any other exceptions, default to BrowserIncorrectPassword.
        """
        if self.login_source == 'direct':
            self.direct_login()
        else:
            # https://www.impots.gouv.fr/actualite/suspension-de-la-connexion-nos-services-pour-les-usagers-utilisant-leur-compte-ameli-sur
            raise BrowserIncorrectPassword(
                "Suite à une maintenance technique sur FranceConnect, l'accès par l'identité numérique Ameli est suspendu jusqu'à nouvel ordre."
            )

        if self.cgu_page.is_here():
            raise ActionNeeded(self.page.get_cgu_message(), action_type=ActionType.ACKNOWLEDGE)

    def direct_login(self):
        self.login_page.go()
        if self.page.is_direct_login_disabled():
            raise BrowserUnavailable()

        if self.ameliconnect_openid.is_here():
            if self.trust_connect and not self.session.cookies.get('trustConnect0'):
                # If for any reason we can't load the state, make sure to keep
                # trust_connect that is valid for 6 months. When it won't be valid anymore,
                # we'll be redirected on regular OTP login after posting the credentials
                # instead of being directly redirected on the user space.
                self.session.cookies.set(
                    'trustConnect0',
                    self.trust_connect,
                    domain='ameliconnect.ameli.fr',
                )

            self.page.login(self.username, self.password)

            if self.ameliconnect_openid.is_here():
                err_msg = self.page.get_error_message().lower()
                browser_user_banned_regexp = re.compile(
                    'accès à votre compte ameli est bloqué'
                    + '|maximum de demandes de code'
                    + '|commander un nouveau code depuis la page de connexion'
                )
                if browser_user_banned_regexp.search(err_msg):
                    raise BrowserUserBanned(err_msg)
                elif 'service momentanément indisponible' in err_msg:
                    # Happens when the given social security number does
                    # not exist. Unexplicit error message shouldn't be raised.
                    raise BrowserIncorrectPassword(bad_fields=['login'])
                elif 'sociale et le code personnel ne correspondent pas' in err_msg:
                    # If the password is wrong, it can be either detected here
                    # or after the OTP is sent. This happens on the website,
                    # sometimes a message is displayed right after submitting
                    # the credentials, sometimes the user is asked to enter
                    # an OTP before a wrong credentials message is shown to him.
                    raise BrowserIncorrectPassword(
                        message=err_msg,
                        bad_fields=['password'],
                    )
                elif 'bad username' in err_msg:
                    raise BrowserIncorrectPassword(bad_fields=['login'])

                if self.page.otp_step() == "":
                    raise AssertionError('Unhandled login step')
                elif self.page.otp_step() == "OTP_NECESSAIRE":
                    self.page.request_otp()
                    if self.page.otp_step() == "SAISIE_OTP":
                        login_form = self.page.get_form(nr=0)
                        self.otp_form_data = dict(login_form)
                        self.otp_form_url = login_form.url
                        raise SentOTPQuestion(
                            'otp_email',
                            medium_type=OTPSentType.EMAIL,
                            message='Veuillez saisir votre code de sécurité (reçu par mail)',
                        )
                    else:
                        raise AssertionError('Unhandled login step "%s"' % (self.page.otp_step()))
                else:
                    raise AssertionError('Unhandled login step "%s"' % (self.page.otp_step()))

        elif self.login_page.is_here():
            # _ct value is necessary for the login
            _ct = self.ct_page.open(method='POST', headers={'FETCH-CSRF-TOKEN': '1'}).get_ct_value()
            self.page.login(self.username, self.password, _ct)

        else:
            raise AssertionError('Unhandled login page')

        self.finalize_login()

    def handle_otp(self):
        if not self.otp_form_data or not self.otp_form_url:
            self.logger.info(
                "We have an OTP but we don't have the OTP form and/or the OTP url."
                + " Restarting the login process..."
            )
            return self.init_login()

        # Put the OTP value inside the form
        otp = self.config['otp_email'].get()
        for index, char in enumerate(otp):
            self.otp_form_data[f"numOTP{index + 1}"] = char

        # Add the device as trusted to avoid triggering 2FA again.
        self.otp_form_data['enrolerDevice'] = 'on'

        self.location(self.otp_form_url, data=self.otp_form_data)  # validate the otp

        self.trust_connect = self.session.cookies['trustConnect0']

        # This is to make sure that we won't run handle_otp() a second time
        # if an ActionNeeded occurs during handle_otp().
        self.otp_form_data = self.otp_form_url = None

        self.finalize_login()

    def finalize_login(self):
        if self.new_password_page.is_here():
            raise BrowserPasswordExpired()
        if self.login_page.is_here():
            err_msg = self.page.get_error_message()
            wrongpass_regex = re.compile(
                'numéro de sécurité sociale et le code personnel'
                + '|compte ameli verrouillé'
                + '|le mot de passe ne correspondent pas'
                + '|informations saisies sont erronées'
            )
            if wrongpass_regex.search(err_msg):
                raise BrowserIncorrectPassword(err_msg)
            raise AssertionError('Unhandled error at login %s' % err_msg)
        elif self.login_continue_page.is_here():
            action_needed_url = self.page.get_action_needed_url()
            if 'as_conditions_generales_page' in action_needed_url:
                raise ActionNeeded(
                    "Veuillez valider les conditions générales d'utilisation sur votre espace en ligne.",
                    action_type=ActionType.ACKNOWLEDGE,
                    locale='fr-FR',
                )
            elif 'as_alerte_page' in action_needed_url:
                # This ActionNeeded asking for the user to confirm
                # his information is skippable.
                self.subscription_page.go()

    @need_login
    def iter_subscription(self):
        self.subscription_page.stay_or_go()
        yield self.page.get_subscription()

    @need_login
    def _iter_details_documents(self, subscription):
        end_date = date.today()

        start_date = end_date - relativedelta(years=1)

        params = {
            'Beneficiaire': 'tout_selectionner',
            'DateDebut': start_date.strftime('%d/%m/%Y'),
            'DateFin': end_date.strftime('%d/%m/%Y'),
            'actionEvt': 'Rechercher',
            'afficherIJ': 'false',
            'afficherInva': 'false',
            'afficherPT': 'false',
            'afficherRS': 'false',
            'afficherReleves': 'false',
            'afficherRentes': 'false',
            'idNoCache': int(time() * 1000),
        }

        # website tell us details documents are available for 6 months
        self.documents_details_page.go(params=params)
        return self.page.iter_documents(subid=subscription.id)

    @need_login
    def _iter_summary_documents(self, subscription):
        # The monthly statements for the last 23 months are available in two parts.
        # The first part contains the last 6 months on an HTML page.
        self.documents_first_summary_page.go()
        for doc in self.page.iter_documents(subid=subscription.id):
            yield doc

        # The second part is retrieved in JSON via this page which displays the next 6 months at each iteration.
        for _ in range(3):
            self.documents_last_summary_page.go()
            for doc in self.page.iter_documents(subid=subscription.id):
                yield doc

    @need_login
    def iter_documents(self, subscription):
        for doc in merge_iterators(
            self._iter_details_documents(subscription),
            self._iter_summary_documents(subscription)
        ):
            yield doc

    @need_login
    def get_profile(self):
        self.subscription_page.go()
        return self.page.get_profile()
