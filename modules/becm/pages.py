# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Julien Veyssier
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


from woob.browser.pages import HTMLPage, LoggedPage
from woob.browser.elements import method, ItemElement
from woob.browser.filters.standard import CleanText, Format
from woob.capabilities import NotAvailable


class LoginPage(AbstractPage):
    PARENT = 'creditmutuel'
    PARENT_URL = 'login'


class AdvisorPage(LoggedPage, HTMLPage):
    @method
    class update_advisor(ItemElement):
        obj_email = CleanText('//table//*[@itemprop="email"]')
        obj_phone = CleanText('//table//*[@itemprop="telephone"]', replace=[(' ', '')])
        obj_mobile = NotAvailable
        obj_fax = CleanText('//table//*[@itemprop="faxNumber"]', replace=[(' ', '')])
        obj_agency = CleanText('//div/*[@itemprop="name"]')
        obj_address = Format('%s %s %s', CleanText('//table//*[@itemprop="streetAddress"]'),
                                        CleanText('//table//*[@itemprop="postalCode"]'),
                                        CleanText('//table//*[@itemprop="addressLocality"]'))
