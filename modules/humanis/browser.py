# Copyright(C) 2016      Jean Walrave
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

from woob_modules.cmes.browser import CmesBrowser


class HumanisBrowser(CmesBrowser):
    login = CmesBrowser.login.with_urls('epsens/(?P<client_space>.*)fr/identification/authentification.html')
    mfa = CmesBrowser.mfa.with_urls('https://www.gestion-epargne-salariale.fr/epsens/fr/epargnants/premiers-pas/authentification-forte/index.html')
