# -*- coding: utf-8 -*-

import re

from woob.tools.capabilities.bank.transactions import FrenchTransaction


class Transaction(FrenchTransaction):
    PATTERNS = [
        # Money arrives on the account:
        (re.compile(r"^VIR\. O/ .* MOTIF: ?(?P<text>.*)$"), FrenchTransaction.TYPE_TRANSFER),
        # Money leaves the account:
        (re.compile(r"^.* VIREMENT SEPA FAVEUR (?P<text>.*)$"), FrenchTransaction.TYPE_TRANSFER),
        # Taxes
        (re.compile(r"^TAXE SUR .*$"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^Prélèvements Sociaux.*$"), FrenchTransaction.TYPE_BANK),
        # Interest income
        (re.compile(r"^Intérêts Créditeurs.*$"), FrenchTransaction.TYPE_BANK),
        (re.compile(r"^REMISE DE CHEQUES.*$"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^VIREMENT D\'ORDRE DE LA NEF.*$"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^MISE A JOUR STOCK.*$"), FrenchTransaction.TYPE_ORDER),
    ]
