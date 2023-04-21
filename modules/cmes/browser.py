# Copyright(C) 2019      Powens
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

from datetime import datetime

from dateutil.relativedelta import relativedelta

from woob.browser import LoginBrowser, URL, need_login
from woob.capabilities.captcha import RecaptchaV3Question
from woob.exceptions import BrowserIncorrectPassword, ActionNeeded

from .pages import (
    LoginPage, AccountsPage, OperationsListPage, OperationPage, ActionNeededPage,
    InvestmentPage, InvestmentDetailsPage,
)


class CmesBrowser(LoginBrowser):
    BASEURL = 'https://www.cic-epargnesalariale.fr'

    login = URL(r'(?P<client_space>.*)fr/identification/authentification.html', LoginPage)

    action_needed = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/premiers-pas/saisir-vos-coordonnees',
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/premiers-pas/vos-services',
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/conditions-generales-d-utilisation/index.html',
        ActionNeededPage
    )

    accounts = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/mon-epargne/situation-financiere-detaillee/index.html',
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/tableau-de-bord/index.html',
        r'(?P<subsite>.*)(?P<client_space>.*)fr/entreprise/tableau-de-bord/index.html',
        AccountsPage
    )

    entreprise_accounts = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/entreprise/situation-financiere-detaillee/index.html',
        AccountsPage
    )

    investments = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/supports/fiche-du-support.html',
        r'(?P<subsite>.*)(?P<client_space>.*)fr/entreprise/supports/synthese-du-support.html',
        InvestmentPage
    )
    investment_details = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/epargnants/supports/epargne-sur-le-support.html',
        InvestmentDetailsPage
    )
    operations_list = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/(?P<sub_space>.*)/operations/index.html',
        OperationsListPage
    )

    operation = URL(
        r'(?P<subsite>.*)(?P<client_space>.*)fr/(?P<sub_space>.*)/operations/consulter-une-operation/index.html\?param_=(?P<idx>\d+)',
        OperationPage
    )

    client_space = 'espace-client/'

    def __init__(self, config, username, password, website, subsite="", *args, **kwargs):
        super(LoginBrowser, self).__init__(*args, **kwargs)
        self.BASEURL = website
        self.username = username
        self.password = password
        self.subsite = subsite
        self.config = config

    @property
    def logged(self):
        return 'IdSes' in self.session.cookies

    def do_login(self):
        self.login.go(client_space=self.client_space)

        if not self.config['captcha_response'].get():
            captcha_site_key = self.page.get_captcha_site_key()
            if captcha_site_key:
                raise RecaptchaV3Question(
                    website_key=captcha_site_key,
                    website_url=self.url,
                    is_enterprise=True,
                    min_score=0.7,
                )

        self.page.login(self.username, self.password, self.config['captcha_response'].get())

        if self.login.is_here():
            raise BrowserIncorrectPassword()

    @need_login
    def iter_accounts(self):
        is_entreprise = False
        self.accounts.go(subsite=self.subsite, client_space=self.client_space)

        if self.action_needed.is_here():
            # Sometimes the page is skippable
            skip_url = self.page.get_skip_url()
            if skip_url:
                self.location(skip_url)
            else:
                msg = self.page.get_message()
                if any((
                    "Merci de renseigner votre adresse e-mail" in msg,
                    "Merci de renseigner votre numéro de téléphone mobile" in msg,
                    "Veuillez accepter les conditions générales d'utilisation" in msg,
                    "Utiliser votre adresse e-mail pour vous connecter" in msg,
                    "Vos services" in msg,
                )):
                    raise ActionNeeded(msg)
                else:
                    raise AssertionError('Unhandled action needed: %s' % msg)

        if 'entreprise' in self.url:
            is_entreprise = True
            self.entreprise_accounts.go(subsite=self.subsite, client_space=self.client_space)

        return self.page.iter_accounts(is_entreprise=is_entreprise)

    @need_login
    def iter_investment(self, account):
        if 'compte courant bloqué' in account.label.lower():
            # CCB accounts have Pockets but no Investments
            return

        if account._entreprise_or_epargnants == 'epargnants':
            self.accounts.stay_or_go(subsite=self.subsite, client_space=self.client_space)
        else:
            self.entreprise_accounts.stay_or_go(subsite=self.subsite, client_space=self.client_space)

        for inv in self.page.iter_investments(account=account):
            # Investments can either be fetched by submitting a form or a direct link.
            if not inv._form_param and not inv._details_url:
                self.logger.info('No available details for investment %s.', inv.label)
                self.accounts.stay_or_go(subsite=self.subsite, client_space=self.client_space)
                yield inv
                continue
            # Go to the investment details to get employee savings attributes
            if inv._form_param:
                form = self.page.get_investment_form(form_param=inv._form_param)
                form.submit()
            elif inv._details_url:
                self.location(inv._details_url)

            if self.investments.is_here():
                # Fetch SRRI, asset category & recommended period
                self.page.fill_investment(obj=inv)

                # Get (1,3,5)-year performance
                performances = {}
                for year in (1, 3, 5):
                    url = self.page.get_form_url()
                    if year == 1:
                        data = {'_FID_DoFilterChart_timePeriod:1Year': ''}
                    elif year == 3:
                        data = {
                            '[t:dbt%3adate;]Data_StartDate': (datetime.today() - relativedelta(years=3)).strftime(
                                '%d/%m/%Y'),
                            '[t:dbt%3adate;]Data_EndDate': datetime.today().strftime('%d/%m/%Y'),
                            '_FID_DoDateFilterChart': '',
                        }
                    elif year == 5:
                        data = {'_FID_DoFilterChart_timePeriod:5Years': ''}
                    self.location(url, data=data)
                    performances[year] = self.page.get_performance()
                inv.performance_history = performances

                # Fetch investment quantity on the 'Mes Avoirs'/'Mon épargne' tab
                url_inv_details = self.page.get_investment_details()
                if url_inv_details:
                    self.location(url_inv_details)
                    self.page.fill_investment(obj=inv, account_type=account.type)
                self.page.go_back()
            else:
                self.logger.info('No available details for investment %s.', inv.label)
                self.accounts.stay_or_go(subsite=self.subsite, client_space=self.client_space)
            yield inv

    @need_login
    def iter_history(self, account):
        self.operations_list.stay_or_go(
            subsite=self.subsite,
            client_space=self.client_space,
            sub_space=account._entreprise_or_epargnants
        )

        for idx in self.page.get_operations_idx(account._entreprise_or_epargnants):
            self.operation.go(
                subsite=self.subsite,
                client_space=self.client_space,
                sub_space=account._entreprise_or_epargnants,
                idx=idx
            )

            if account._entreprise_or_epargnants == 'epargnants':
                for tr in self.page.get_transactions():
                    if account.label == tr._account_label:
                        yield tr
            else:
                yield from self.page.get_entreprise_transactions()

    @need_login
    def iter_pocket(self, account):
        self.accounts.stay_or_go(subsite=self.subsite, client_space=self.client_space)
        if 'compte courant bloqué' in account.label.lower():
            # CCB accounts have a specific table containing only Pockets
            for pocket in self.page.iter_ccb_pockets(account=account):
                yield pocket
        else:
            for inv in self.page.iter_investments(account=account):
                if not inv._form_param:
                    continue
                # Go to the investment details to get employee savings attributes
                form = self.page.get_investment_form(form_param=inv._form_param)
                form.submit()
                if self.investments.is_here():
                    try:
                        self.page.go_investment_details()
                        for pocket in self.page.iter_pockets(inv=inv):
                            yield pocket
                    finally:
                        self.page.go_back()
