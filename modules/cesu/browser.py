# flake8: compatible

# Copyright(C) 2020      Ludovic LANGE
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

import calendar
from datetime import datetime

from dateutil.relativedelta import relativedelta

from woob.browser import URL, LoginBrowser, need_login
from woob.browser.exceptions import ClientError
from woob.capabilities.bill import Subscription
from woob.exceptions import BrowserIncorrectPassword

from .pages import (
    CurrentFiscalAdvantagePage,
    DirectDebitDownloadPage,
    DirectDebitsDetailPage,
    DirectDebitsHeaderPage,
    DirectDebitSummaryPage,
    EmployeesDashboardPage,
    EmployeesPage,
    EmployerPage,
    HomePage,
    LastDayMonthPage,
    LoginPage,
    PayslipDownloadPage,
    RegistrationDashboardPage,
    RegistrationPage,
    StatusPage,
    TaxCertificateDownloadPage,
    TaxCertificatesPage,
)


class CesuBrowser(LoginBrowser):
    BASEURL = "https://www.cesu.urssaf.fr"

    login = URL(r"/cesuwebdec/authentication$", LoginPage)
    homepage = URL(r"/info/accueil\.login\.do$", HomePage)
    logout = URL(r"/cesuwebdec/deconnexion$")
    status = URL(r"/cesuwebdec/status", StatusPage)

    employer = URL(r"/cesuwebdec/employeursIdentite/(?P<employer>.*)", EmployerPage)
    employees = URL(r"/cesuwebdec/employeurs/(?P<employer>.*)/salaries", EmployeesPage)
    employees_dashboard = URL(
        r"/cesuwebdec/salariesTdb?pseudoSiret=(?P<employer>.*)&maxResult=8", EmployeesDashboardPage
    )

    registrations = URL(r"/cesuwebdec/employeurs/(?P<employer>.*)/declarationsby\?.*", RegistrationPage)
    registrations_dashboard = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/declarationsTdBby\?.*", RegistrationDashboardPage
    )

    direct_debits_summary = URL(r"/cesuwebdec/employeurs/(?P<employer>.*)/recapprelevements", DirectDebitSummaryPage)
    direct_debits_header = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/entetePrelevements\?.*", DirectDebitsHeaderPage
    )
    direct_debits_detail = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/detailPrelevements\?periode=202001&type=IPVT&reference=0634675&idPrelevement=0",
        DirectDebitsDetailPage,
    )
    direct_debit_download = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/editions/avisPrelevement\?reference=(?P<reference>.*)&periode=(?P<period>.*)&type=(?P<type>.*)",
        DirectDebitDownloadPage,
    )

    current_fiscal_advantage = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/avantagefiscalencours", CurrentFiscalAdvantagePage
    )
    last_day_month = URL(r"/cesuwebdec/employeurs/(?P<employer>.*)/dernierJourOuvreMois", LastDayMonthPage)
    payslip_download = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/editions/bulletinSalairePE\?refDoc=(?P<ref_doc>.*)",
        PayslipDownloadPage,
    )
    tax_certificates = URL(r"/cesuwebdec/employeurs/(?P<employer>.*)/attestationsfiscales", TaxCertificatesPage)
    tax_certificate_download = URL(
        r"/cesuwebdec/employeurs/(?P<employer>.*)/editions/attestation_fiscale_annee\?periode=(?P<year>.*)",
        TaxCertificateDownloadPage,
    )

    employer = None
    compteur = 0

    def do_login(self):
        self.session.cookies.clear()
        self.session.headers.update(
            {
                "Accept": "*/*",
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

        try:
            self.login.go(
                json={
                    "username": self.username,
                    "password": self.password,
                }
            )
        except ClientError as error:
            response = error.response.json()

            error_messages_list = response.get("listeMessages", [])

            for error_message in error_messages_list:
                if error_message.get("contenu", "") == "Identifiant / mot de passe non reconnus":
                    raise BrowserIncorrectPassword(error_message["contenu"])

            raise

        self.status.go()
        self.employer = self.page.get_object().get("numero")

    def do_logout(self):
        self.logout.go()
        self.session.cookies.clear()

    @need_login
    def iter_subscription(self):
        self.employees.go(employer=self.employer)

        yield from self.page.iter_subscriptions()

        s = Subscription()
        s.label = "Prélèvements"
        s.id = "prelevements"
        s._type = s.id
        yield s

        s = Subscription()
        s.label = "Attestations fiscales"
        s.id = "taxcertificates"
        s._type = s.id
        yield s

    def _search_registrations(self, subscription, begin_date, end_date, num_start, step):
        self.registrations.go(
            employer=self.employer,
            params={
                "numInterneSalarie": subscription.id,
                "dtDebutRecherche": begin_date.strftime("%Y%m%d"),
                "dtFinRecherche": end_date.strftime("%Y%m%d"),
                "numStart": num_start,
                "nbAffiche": step,
                "numeroOrdre": self.compteur,
            },
        )
        self.compteur += 1

    def _search_direct_debits(self, begin_date, end_date):
        self.direct_debits_header.go(
            employer=self.employer,
            params={
                "dtDebut": begin_date.strftime("%Y%m%d"),
                "dtFin": end_date.strftime("%Y%m%d"),
                "numeroOrdre": self.compteur,
                "nature": "",
            },
        )
        self.compteur += 1

    @need_login
    def iter_documents(self, subscription):
        self.compteur = 0

        if subscription._type == "employee":
            end_date = datetime.today()
            # 5 years maximum
            begin_date = end_date - relativedelta(years=+5)

            has_results = True
            num_start = 0
            step = 24

            while has_results:
                self._search_registrations(subscription, begin_date, end_date, num_start, step)

                num_start += step

                has_results = len(self.page.get_objects()) > 0

                yield from self.page.iter_documents(subscription=subscription.id, employer=self.employer)

        elif subscription._type == "prelevements":
            # Start end of month
            end_date = datetime.today()
            end_date += relativedelta(
                day=calendar.monthrange(end_date.year, end_date.month)[1],
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            # 1 year maximum ; beginning of month
            begin_date = end_date - relativedelta(years=+1, day=1)

            self._search_direct_debits(begin_date, end_date)

            has_results = len(self.page.get_objects()) > 0

            yield from self.page.iter_documents(subscription=subscription.id, employer=self.employer)

        elif subscription._type == "taxcertificates":
            self.tax_certificates.go(employer=self.employer)
            yield from self.page.iter_documents(subscription=subscription.id, employer=self.employer)
