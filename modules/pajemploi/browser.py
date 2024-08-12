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


from woob.browser import URL, need_login
from woob.capabilities.bill import Subscription
from woob.exceptions import BrowserIncorrectPassword
from woob_modules.franceconnect.browser import FranceConnectBrowser

from .pages import (
    AjaxDetailSocialInfoPage,
    CotisationsDownloadPage,
    DeclarationDetailPage,
    DeclarationListPage,
    DeclarationSetupPage,
    EmployeesPage,
    ErrorMaintenancePage,
    FranceConnectLoginPage,
    FranceConnectRedirectPage,
    HomePage,
    LoginPage,
    MonthlyReportDownloadPage,
    PayslipDownloadPage,
    RegistrationRecordDownloadPage,
    TaxCertificatesPage,
)


class PajemploiBrowser(FranceConnectBrowser):
    BASEURL = "https://www.pajemploi.urssaf.fr"

    fc_login = URL(r"/pajeweb/login-franceconnect.htm", FranceConnectLoginPage)
    france_connect_redirect = URL(r"https://app.franceconnect.gouv.fr/api/v1/authorize\?.*", FranceConnectRedirectPage)
    logout = URL(r"/pajeweb/j_spring_security_logout$", r"/pajeweb/quit.htm$")
    fc_logout = URL(r"/pajeweb/logout-franceconnect.htm$")

    login = URL(
        r"/pajeweb/logindec\.htm$",
        r"/pajeweb/login-pajemploi\.htm$",
        r"/info/accueil.html$",
        r"/portail/accueil.html$",
        r"/pajewebinfo/cms/sites/pajewebinfo/accueil.html$",
        r"/pajeweb/connect.htm$",
        r"/pajeweb/home.jsp$",
        LoginPage,
    )

    homepage = URL(
        r"/info/accueil.html$",
        r"/portail/accueil.html$",
        r"/pajewebinfo/cms/sites/pajewebinfo/accueil.html$",
        r"/pajeweb/connect.htm$",
        r"/pajeweb/home.jsp$",
        HomePage,
    )

    employees = URL(r"/pajeweb/listesala/gerersala.htm$", EmployeesPage)

    tax_certificates = URL(r"/pajeweb/atfirecap.htm$", TaxCertificatesPage)

    declaration_setup = URL(r"/pajeweb/listeVSssl.jsp$", DeclarationSetupPage)
    declaration_list = URL(r"/pajeweb/ajaxlistevs.jsp$", DeclarationListPage)
    declaration_detail = URL(r"/pajeweb/recapitulatifPrestationFiltre.htm$", DeclarationDetailPage)
    payslip_download = URL(r"/pajeweb/paje_bulletinsalaire.pdf\?ref=(?P<refdoc>.*)", PayslipDownloadPage)
    monthly_report_download = URL(r"/pajeweb/decla/saisie/afficherReleveMensuel.htm$", MonthlyReportDownloadPage)
    registration_record_download = URL(r"/pajeweb/afficherCertificat.htm$", RegistrationRecordDownloadPage)
    cotisations_download = URL(r"/pajeweb/paje_decomptecotiempl.pdf?ref=(?P<refdoc>.*)", CotisationsDownloadPage)
    ajax_detail_social_info = URL(r"/pajeweb/ajaxdetailvs.jsp$", AjaxDetailSocialInfoPage)
    error_maintenance = URL(r"/pajeweb/logindec.htm", ErrorMaintenancePage)

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.login_source = config["login_source"].get()

    def do_login(self):
        self.session.cookies.clear()
        self.login.go()
        if self.login_source == "direct":
            self.page.login(self.username, self.password, "XXXXX")
        elif self.login_source == "fc_impots":
            self.fc_login.go()
            self.login_impots()
            self.page = self.homepage.handle(self.response)
            if not isinstance(self.page, HomePage):
                raise AssertionError(f"Unexpected page: {self.page} after FranceConnect redirects")
        else:
            raise AssertionError(f"Unexpected login source: {self.login_source}")
        if not self.page.logged:
            raise BrowserIncorrectPassword()

    def do_logout(self):
        if self.login_source == "direct":
            self.logout.go()
        else:
            self.fc_logout.go()
        self.session.cookies.clear()

    @need_login
    def iter_subscription(self):
        self.employees.go()

        s = Subscription()
        s.label = "Attestations fiscales"
        s.id = "taxcertificates"
        s._type = s.id
        yield s

        yield from self.page.iter_subscriptions(subscriber=None)

    @need_login
    def iter_documents(self, subscription):
        if subscription._type == "employee":

            self.declaration_setup.go()
            data = self.page.get_data(subscription)
            self.declaration_list.go(data=data)

            for proto_doc in self.page.iter_documents(subscription_id=subscription.id):
                data = {"refdoc": proto_doc._refdoc, "norng": proto_doc._norng}
                self.declaration_detail.go(data=data)
                for doc in self.page.iter_documents(proto_doc, subscription):
                    doc._previous_data = data
                    doc._previous_page = self.declaration_detail
                    yield doc

        elif subscription._type == "taxcertificates":

            self.tax_certificates.go()
            for doc in self.page.iter_documents(subscription=subscription):
                yield doc

    def download_document(self, document):
        if hasattr(document, "_need_refresh_previous_page") and document._need_refresh_previous_page:
            document._previous_page.go(data=document._previous_data)
        data = {}
        if hasattr(document, "_ref"):
            data["ref"] = document._ref
        return self.open(document.url, data=data).content
