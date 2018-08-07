# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals


import re

from lxml import html

from weboob.browser.pages import HTMLPage, LoggedPage, JsonPage, AbstractPage
from weboob.browser.elements import method, ItemElement, TableElement
from weboob.browser.filters.standard import CleanText, Date, CleanDecimal, Regexp, Format, Field
from weboob.browser.filters.json import Dict
from weboob.browser.filters.html import TableCell
from weboob.capabilities.bank import Investment
from weboob.capabilities.profile import Profile
from weboob.capabilities import NotAvailable
from weboob.tools.compat import unicode

def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)

def MyStrip(x, xpath='.'):
    if isinstance(x, unicode):
        return CleanText(xpath)(html.fromstring("<p>%s</p>" % x))
    elif isinstance(x, bytes):
        x = x.decode('utf-8')
        return CleanText(xpath)(html.fromstring("<p>%s</p>" % x))
    else:
        return CleanText(xpath)(html.fromstring(CleanText('.')(x)))


class RedirectPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'redirect'


class EntryPage(HTMLPage):
    pass


class LoginPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'login'


class AccountTypePage(LoggedPage, JsonPage):
    def get_account_type(self):
        account_type = CleanText(Dict('donnees/id'))(self.doc)
        if account_type == "menu_espace_perso_part":
            return "particuliers"
        elif account_type == "menu_espace_perso_pro":
            return "professionnels"
        elif account_type == "menu_espace_perso_ent":
            return "entreprises"


class ProfilePage(LoggedPage, JsonPage):
    def get_profile(self):
        profile = Profile()
        profile.name = Format('%s %s', CleanText(Dict('donnees/nom')), CleanText(Dict('donnees/prenom'), default=''))(self.doc)
        return profile


class AccountsPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'accounts'

    def make__args_dict(self, line):
        return {'_eventId': 'clicDetailCompte',
                '_ipc_eventValue':  '',
                '_ipc_fireEvent':   '',
                'execution': self.get_execution(),
                'idCompteClique':   line[self.COL_ID],
               }


class CDNBasePage(HTMLPage):
   def get_from_js(self, pattern, end_pattern, is_list=False):
       """
       find a pattern in any javascript text
       """
       for script in self.doc.xpath('//script'):
           txt = script.text
           if txt is None:
               continue

           start = txt.find(pattern)
           if start < 0:
               continue

           values = []
           while start >= 0:
               start += len(pattern)
               end = txt.find(end_pattern, start)
               values.append(txt[start:end])

               if not is_list:
                   break

               start = txt.find(pattern, end)
           return ','.join(values)

   def get_execution(self):
       return self.get_from_js("name: 'execution', value: '", "'")

   def iban_go(self):
       return '%s%s' % ('/vos-comptes/IPT/cdnProxyResource', self.get_from_js('C_PROXY.StaticResourceClientTranslation( "', '"'))


class ProIbanPage(CDNBasePage):
    pass


class AVPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'av'


class PartAVPage(AVPage):
    pass


class ProAccountsPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'proaccounts'


class IbanPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'iban'


class TransactionsPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'transactions'

    @method
    class get_deposit_investment(TableElement):
        item_xpath = '//table[@class="datas"]//tr[position()>1]'
        head_xpath = '//table[@class="datas"]//tr[@class="entete"]/td/b'

        col_label = u'Libellé'
        col_quantity = u'Quantité'
        col_unitvalue = re.compile(u"Valeur liquidative")
        col_valuation = re.compile(u"Montant")

        class item(ItemElement):
            klass = Investment
            obj_label = CleanText(TableCell('label'))
            obj_quantity = MyDecimal(CleanText(TableCell('quantity')))
            obj_valuation = MyDecimal(TableCell('valuation'))
            obj_unitvalue = MyDecimal(TableCell('unitvalue'))
            def obj_vdate(self):
                if Field('unitvalue') is NotAvailable:
                    vdate = Date(dayfirst=True, default=NotAvailable)\
                       .filter(Regexp(CleanText('.'), '(\d{2})/(\d{2})/(\d{4})', '\\3-\\2-\\1', default=NotAvailable)(TableCell('unitvalue')(self))) or \
                       Date(dayfirst=True, default=NotAvailable)\
                       .filter(Regexp(CleanText('//tr[td[span[b[contains(text(), "Estimation du contrat")]]]]/td[2]'),
                                      '(\d{2})/(\d{2})/(\d{4})', '\\3-\\2-\\1', default=NotAvailable)(TableCell('unitvalue')(self)))
                    return vdate


class ProTransactionsPage(AbstractPage):
    PARENT = 'creditdunord'
    PARENT_URL = 'protransactions'
