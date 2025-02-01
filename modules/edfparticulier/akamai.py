# Copyright(C) 2022  Budget Insight
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

try:
    from woob.tools.antibot.akamai import AkamaiHTMLPage, AkamaiMixin

except ModuleNotFoundError:
    from woob.browser.pages import HTMLPage

    # if you encounter antiscraping from akamai, you should implement here code to
    # circumvent their blocking

    class FakeAkamaiHTMLPage(HTMLPage):
        def get_akamai_url(self):
            return ""

    class FakeAkamaiSolver:
        html_doc = None

    class FakeAkamaiMixin:
        def get_akamai_solver(self, *args, **kwargs):
            return FakeAkamaiSolver()

        def post_sensor_data(self, *args, **kwargs):
            pass

        def resolve_akamai_challenge(self, html_doc=None):
            """
            this function is a simple helper to not do too much specific things in you browser
            call this function if you don't have to specify any attribute
            or need to perform specific check
            """
            akamai_url = self.page.get_akamai_url()
            akamai_solver = self.get_akamai_solver(akamai_url, self.url)
            if html_doc:
                akamai_solver.html_doc = html_doc
            cookie_abck = self.session.cookies["_abck"]
            self.post_sensor_data(akamai_solver, cookie_abck)

    AkamaiMixin = FakeAkamaiMixin

    AkamaiHTMLPage = FakeAkamaiHTMLPage
