# Copyright(C) 2022-2023 Powens
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

from dateutil.relativedelta import relativedelta
from dateutil.tz import gettz

from woob.browser.elements import (
    ItemElement, ListElement, TableElement, method,
)
from woob.browser.filters.html import Attr, TableCell
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce, Currency, Date, Format, Regexp,
)
from woob.browser.pages import HTMLPage, LoggedPage, RawPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Bill, Subscription
from woob.capabilities.profile import Person
from woob.tools.date import now_as_tz


class BaseHTMLPage(HTMLPage):
    def get_error_message(self):
        return Coalesce(
            CleanText('//div[contains(@class, "alerte")]', default=None),
            CleanText('//div[@class="blocmsg err"]', default=None),
            default=None,
        )(self.doc)


class LoginPage(BaseHTMLPage):
    def get_site_key(self):
        return Attr(
            '//div[@class="g-recaptcha"]',
            'data-sitekey',
            default=None,
        )(self.doc)

    def do_login(self, username, password, captcha_response):
        form = self.get_form(id='bloc_ident')
        form['_cm_user'] = username
        form['_cm_pwd'] = password
        form['g-recaptcha-response'] = captcha_response
        form.submit()


class HomePage(LoggedPage, RawPage):
    pass


class SubscriptionPage(LoggedPage, BaseHTMLPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_label = CleanText(
            '//div[@id="C:I:root"]//span',
            default=NotAvailable,
        )

        def obj_renewdate(self):
            # "le XX de chaque mois"
            renew_day = CleanDecimal.SI(Regexp(
                CleanText(
                    '//span[contains(text(), "Renouvellement de votre forfait")]'
                    + '/following-sibling::span',
                ),
                r'le ([0-9]+) de chaque mois',
                default=None,
            ))(self)

            if renew_day is None:
                return NotAvailable

            renew_date = now_as_tz(tzinfo=gettz('Europe/Paris')).date()
            if renew_date.day >= renew_day:
                renew_date += relativedelta(months=1)

            try:
                return renew_date.replace(day=renew_day)
            except ValueError:
                # Some subscriptions have a renew day set as the 31st.
                # This day of the month doesn't exist for all months, so
                # we suppose the renew date is on the 1st of the month
                # after in these cases.
                renew_date += relativedelta(months=1)
                return renew_date.replace(day=1)


class OrderBillsPage(LoggedPage, BaseHTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@id="C:F9:D"]/div[@class="a_blocfctl"]'

        class item(ItemElement):
            klass = Bill

            obj_id = Regexp(
                Attr('.//input[@type="submit"]', 'name'),
                r'cleCommande:([0-9]+)_',
                default='',
            )
            obj__from = 'orders'

            obj_format = 'pdf'

            obj_date = Date(
                Regexp(
                    CleanText('.//p[@class="_c1 a_titre2 _c1"]', default=''),
                    r'([0-9]+/[0-9]+/[0-9]+)',
                ),
                dayfirst=True,
                default=NotAvailable,
            )
            obj_total_price = CleanDecimal.French(
                './/tr[./th[text()="Montant"]]/td',
                default=NotAvailable,
            )
            obj_currency = Currency(
                './/tr[./th[text()="Montant"]]/td',
                default=NotAvailable,
            )

    def download_document(self, id_):
        for _submit in self.doc.xpath(
            '//div[@id="C:F9:D"]//input[@name=$id_]',
            id_=f'_FID_DoExportPdf_cleCommande:{id_}_typeDocument:Commande',
        ):
            break
        else:
            # Document has not been found on the current page.
            return

        form = self.get_form(
            id='C:P:F',
            submit=_submit,
        )

        return self.browser.open(form.request).content


class PeriodicBillsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(TableElement):
        head_xpath = '//div[@id="C:F6:expContent"]//tr/th'
        item_xpath = '//div[@id="C:F6:expContent"]//tr[./td[@class]]'

        col_date = 'Date'
        col_bills = 'Factures'
        col_amount = 'Montant'

        class item(ItemElement):
            klass = Bill

            def obj_id(self):
                cell = TableCell('bills')(self)[0]
                return Regexp(
                    Attr('./input', 'name'),
                    r'.*:([0-9]+)$',
                )(cell)

            obj__from = 'periodic'
            obj_format = 'pdf'

            obj_date = Date(
                CleanText(TableCell('date')),
                dayfirst=True,
                default=NotAvailable,
            )
            obj_total_price = CleanDecimal.French(
                TableCell('amount'),
                default=NotAvailable,
            )
            obj_currency = Currency(
                TableCell('amount'),
                default=NotAvailable,
            )

    def download_document(self, id_):
        for _submit in self.doc.xpath(
            '//div[@id="C:F6:D"]//input[@name=$id_]',
            id_=f'_FID_DoExportPDF_numeroFacture:{id_}',
        ):
            break
        else:
            # Document has not been found on the current page.
            return

        form = self.get_form(
            id='C:P:F',
            submit=_submit,
        )

        return self.browser.open(form.request).content


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_gender = CleanText(
            '//th[label[@for="C:Civilite"]]/following-sibling::td',
            default=NotAvailable,
        )
        obj_lastname = CleanText(
            '//th[label[@for="C:Nom"]]/following-sibling::td',
            default=NotAvailable,
        )
        obj_firstname = CleanText(
            '//th[label[@for="C:Prenom"]]/following-sibling::td',
            default=NotAvailable,
        )
        obj_birth_date = Date(
            CleanText(
                '//th[label[@for="C:DateNaissance"]]/following-sibling::td',
                default=NotAvailable,
            ),
            dayfirst=True,
            default=NotAvailable,
        )

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_street = CleanText(
                Format(
                    '%s\n%s',
                    CleanText(
                        '//th[label[@for="C:Adresse"]]/following-sibling::td',
                        default='',
                    ),
                    CleanText(
                        '//th[label[@for="C:ComplementAdresse"]]'
                        + '/following-sibling::td',
                        default='',
                    ),
                ),
                default=NotAvailable,
            )
            obj_postal_code = CleanText(
                '//th[label[@for="C:CodePostal"]]/following-sibling::td',
                default=NotAvailable,
            )
            obj_city = CleanText(
                '//th[label[@for="C:Ville"]]/following-sibling::td',
                default=NotAvailable,
            )
            obj_country = CleanText(
                '//th[label[@for="C:Pays"]]/following-sibling::td',
                default=NotAvailable,
            )

        obj_email = CleanText(
            '//th[label[@for="C:EmailContact"]]/following-sibling::td',
            default=NotAvailable,
        )
        obj_phone = CleanText(
            '//th[label[@for="C:TelephoneMobile"]]/following-sibling::td',
            default=NotAvailable,
        )
