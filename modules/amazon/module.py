# Copyright(C) 2017      Théo Dorée
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

from collections import OrderedDict
from urllib.parse import urljoin

from woob.capabilities.base import NotAvailable, find_object
from woob.capabilities.bill import (
    CapDocument,
    Document,
    DocumentCategory,
    DocumentNotFound,
    DocumentTypes,
    Subscription,
)
from woob.tools.backend import BackendConfig, Module
from woob.tools.pdf import html_to_pdf
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import AmazonBrowser
from .de.browser import AmazonDeBrowser
from .en.browser import AmazonEnBrowser
from .uk.browser import AmazonUkBrowser


__all__ = ["AmazonModule"]


class AmazonModule(Module, CapDocument):
    NAME = "amazon"
    DESCRIPTION = "Amazon"
    MAINTAINER = "Théo Dorée"
    EMAIL = "tdoree@budget-insight.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"

    website_choices = OrderedDict(
        [
            (k, "%s (%s)" % (v, k))
            for k, v in sorted(
                {
                    "www.amazon.com": "Amazon.com",
                    "www.amazon.fr": "Amazon France",
                    "www.amazon.de": "Amazon.de",
                    "www.amazon.co.uk": "Amazon UK",
                }.items()
            )
        ]
    )

    BROWSERS = {
        "www.amazon.fr": AmazonBrowser,
        "www.amazon.com": AmazonEnBrowser,
        "www.amazon.de": AmazonDeBrowser,
        "www.amazon.co.uk": AmazonUkBrowser,
    }

    CONFIG = BackendConfig(
        Value("website", label="Website", choices=website_choices, default="www.amazon.com"),
        ValueBackendPassword("email", label="Username", masked=False),
        ValueBackendPassword("password", label="Password"),
        ValueTransient("captcha_response", label="Captcha Response"),
        ValueTransient("pin_code", label="OTP response"),
        ValueTransient("request_information"),
        ValueTransient("resume"),
    )

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.SHOPPING}

    def create_default_browser(self):
        self.BROWSER = self.BROWSERS[self.config["website"].get()]
        return self.create_browser(self.config)

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def get_document(self, _id):
        subid = _id.rsplit("_", 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def get_pdf_from_cache_or_download_it(self, document):
        summary_document = self.browser.summary_documents_content.pop(document.id, None)
        if summary_document:
            return summary_document
        return self.browser.open(document.url).content

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if document.url is NotAvailable:
            return
        return self.get_pdf_from_cache_or_download_it(document)

    def download_document_pdf(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if document.url is NotAvailable:
            return
        if document.format == "pdf":
            return self.get_pdf_from_cache_or_download_it(document)
        # We can't pass the html document we saved before as a string since there is a freeze when wkhtmltopdf
        # takes a string
        url = urljoin(self.browser.BASEURL, document.url)
        return html_to_pdf(self.browser, url=url)
