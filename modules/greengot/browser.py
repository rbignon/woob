# -*- coding: utf-8 -*-

# Copyright(C) 2024      Pierre BOULC'H
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

import json
from datetime import datetime

from woob.capabilities.bank import (
    Account, Transaction,
    AccountNotFound, AccountType,
)
from woob.browser.browsers import APIBrowser
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.browsers import need_login
from woob.exceptions import (
    OTPSentType, SentOTPQuestion,
)
from woob.capabilities.base import find_object


class GreenGotBrowser(TwoFactorBrowser, APIBrowser):
    BASEURL = 'https://api.retail.green-got.com'

    BANK_NAME = 'GreenGot'

    __states__ = (
        'access_token',
    )

    def __init__(self, config, email, *args, **kwargs):
        super().__init__(config, email, "", *args, **kwargs)
        self.email = email

        self.AUTHENTICATION_METHODS = {
            'smscode': self.handle_otp,
            'emailcode': self.handle_otp,
        }
        self.access_token = None

    def deinit(self):
        return super().deinit()

    def do_request(self, payload, endpoint='/graphql', headers=None):
        if headers is None:
            headers = {}
        self.session.headers = headers
        return self.request(endpoint, data=payload)

    def do_open(self, payload, endpoint='/graphql', headers=None):
        if headers is None:
            headers = {}
        self.session.headers = headers
        return self.open(url=endpoint, data=payload)

    def do_login(self):
        if self.access_token is None:
            if self.config["smscode"].get() is None:
                payload = {
                    "operationName": "UserSignInMutation",
                    "query": "mutation UserSignInMutation($input: SignInInput!) {\n  user_signIn(input: $input) {\n    __typename\n    ... on LoginCodeJustSent {\n      signInMethod\n      __typename\n    }\n    ... on SignInSuccess {\n      signInMethod\n      __typename\n    }\n  }\n}",
                    "variables": {
                        "input": {
                            "email": self.email,
                        },
                    },
                }
                self.do_request(payload)
                raise SentOTPQuestion(
                    'smscode',
                    medium_type=OTPSentType.SMS,
                    message='Veuillez entrer le code reçu par SMS',
                )
            elif self.config["emailcode"].get() is None:
                raise SentOTPQuestion(
                    'emailcode',
                    medium_type=OTPSentType.EMAIL,
                    message='Veuillez entrer le code reçu par email',
                )
            else:
                self.get_token()

    def get_token(self):
        payload = {
            "operationName": "UserCheckLoginCodeMutation",
            "query": "mutation UserCheckLoginCodeMutation($input: CheckLoginCodeInput!) {\n  user_checkLoginCode(input: $input) {\n    __typename\n    ... on CheckLoginCodeSuccess {\n      idToken\n      user: user_v2 {\n        id\n        firstName\n        lastName\n        phoneNumber\n        intercomUserHash {\n          ios\n          android\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n  }\n}",
            "variables": {
                "input": {
                    "email": self.config["login"].get(),
                    "oneTimeCode": self.config["emailcode"].get(),
                    "smsCode": self.config["smscode"].get(),
                },
            },
        }
        response = self.do_request(payload)
        self.access_token = response["data"]["user_checkLoginCode"]["idToken"]

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})

        if self.access_token is not None:
            headers['Authorization'] = 'Bearer %s' % self.access_token

        headers['Accept'] = 'application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed'

        req = super().build_request(*args, **kwargs)
        return req

    def raise_for_status(self, response):
        if '"code":"UNAUTHORIZED' in response.content.decode("utf-8"):
            self.access_token = None
        return super().raise_for_status(response)

    @need_login
    def iter_accounts(self):
        payload = {
            "operationName": "AccountsScreenQuery",
            "query": "query AccountsScreenQuery {\n  ...Savings\n  ...Suggestions\n  ...KYCStatus\n  wallets {\n    edges {\n      node {\n        ...WalletListCardFields\n        __typename\n      }\n      __typename\n    }\n    pageInfo {\n      startCursor\n      endCursor\n      hasNextPage\n      __typename\n    }\n    __typename\n  }\n  user: user_v2 {\n    id\n    ...Balance\n    __typename\n  }\n  accounts {\n    accountRef\n    __typename\n  }\n  ...AccountListCardFragment\n}\nfragment KYCStatus on Query {\n  completedOnboardings: onboardings(filter: {statuses: [COMPLETED]}) {\n    id\n    topUpAmount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  user: user_v2 {\n    id\n    verification {\n      status\n      __typename\n    }\n    firstName\n    __typename\n  }\n  __typename\n}\nfragment AmountFragment on Amount {\n  value\n  currency\n  exponent\n  __typename\n}\nfragment Balance on User_v2 {\n  ... on User_v2 @defer {\n    balance {\n      amount {\n        ...AmountFragment\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment AccountListCardFragment on Query {\n  accounts {\n    __typename\n    accountRef\n    ...AccountFields\n    balance {\n      amount {\n        ...AmountFragment\n        __typename\n      }\n      __typename\n    }\n  }\n  completedOnboardings: onboardings(filter: {statuses: [COMPLETED]}) {\n    __typename\n    id\n    ...OnboardingFields\n    topUpAmount {\n      ...AmountFragment\n      __typename\n    }\n  }\n  __typename\n}\nfragment OnboardingFields on Onboarding {\n  id\n  name\n  icon\n  topUpAmount {\n    ...AmountFragment\n    __typename\n  }\n  __typename\n}\nfragment AccountFields on Account {\n  name\n  accountRef\n  cards(filter: {latest: true}) {\n    design\n    designSymbol\n    __typename\n  }\n  balance {\n    amount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment WalletListCardFields on Wallet {\n  ...WalletFields\n  balance {\n    amount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment WalletFields on Wallet {\n  id\n  name\n  icon\n  balance {\n    amount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment Suggestions on Query {\n  accounts {\n    accountRef\n    __typename\n  }\n  user: user_v2 {\n    id\n    productSuggestions\n    __typename\n  }\n  __typename\n}\nfragment Savings on Query {\n  investments: investments_v2 {\n    __typename\n    status\n    subscriptionId\n    ...ContractFields\n  }\n  investmentSubscription {\n    subscriptionId\n    status\n    ...SubscriptionFields\n    __typename\n  }\n  __typename\n}\nfragment ContractFields on InvestmentContract {\n  subscriptionId\n  ... @defer {\n    details: detailsV2 {\n      __typename\n      ... on InvestmentDetails {\n        amount {\n          ...AmountFragment\n          __typename\n        }\n        __typename\n      }\n    }\n    __typename\n  }\n  __typename\n}\nfragment SubscriptionFields on InvestmentSubscription_v2 {\n  subscriptionId\n  status\n  __typename\n}",
        }
        response = self.do_open(payload)

        # Response is a mixed body with two json. For example:
        # ---
        # Content-Type: application/json; charset=utf-8
        # Content-Length: 1804
        #
        # {"data":{"__typename":"Query","investmentSubscription":null,"completedOnboardings":[],"investments":[],"user":{"__typename":"User_v2","id":"hfudhu","firstName":"John","productSuggestions":["SOLE_TRADER_ACCOUNT","JOINT_ACCOUNT","LIFE_INSURANCE"],"verification":{"__typename":"Verification","status":"APPROVED"}},"accounts":[{"__typename":"Account","accountRef":"INDIVIDUAL","name":"Compte personnel","cards":[{"__typename":"Card","design":"WOOD","designSymbol":null}],"balance":{"__typename":"Balance","amount":{"__typename":"Amount","value":50000,"currency":"EUR","exponent":null}}}],"wallets":{"__typename":"WalletsConnection","pageInfo":{"__typename":"PageInfo","startCursor":"wallet_LccmbpL7Yzv5KrMR_HNCFgBmKqdfsds","endCursor":"wallet_r89YnXzhFs0OfWFdsdhjydxa0eBX0c2y8Ysdsdqdsqc","hasNextPage":false},"edges":[{"__typename":"WalletEdge","node":{"__typename":"Wallet","id":"wallet_LccmbpL7Yfezzvuyvzv5KrMR_HNCFgBmKqk","name":"Test 1","icon":"😁","balance":{"__typename":"Balance","amount":{"__typename":"Amount","value":0,"currency":"EUR","exponent":null}}}},{"__typename":"WalletEdge","node":{"__typename":"Wallet","id":"wallet_XRL0K-moX0P4_Ruqw54Pa4hmrezckjdfdssgjhhfbez1Y","name":"Test 3","icon":"👛","balance":{"__typename":"Balance","amount":{"__typename":"Amount","value":0,"currency":"EUR","exponent":null}}}},{"__typename":"WalletEdge","node":{"__typename":"Wallet","id":"wallet_ytb6UulBt1D2j6dhssjREsPXtN0803Qs1k","name":"Test2","icon":"😃","balance":{"__typename":"Balance","amount":{"__typename":"Amount","value":0,"currency":"EUR","exponent":null}}}},{"__typename":"WalletEdge","node":{"__typename":"Wallet","id":"wallet_r89YnXzhFs0OfWFa0eBX0c2yGRZCGHE8Yc","name":"Test4","icon":"👛","balance":{"__typename":"Balance","amount":{"__typename":"Amount","value":0,"currency":"EUR","exponent":null}}}}]}},"hasNext":true}
        # ---
        # Content-Type: application/json; charset=utf-8
        # Content-Length: 197
        #
        # {"incremental":[{"data":{"__typename":"User_v2","balance":{"__typename":"Balance","amount":{"__typename":"Amount","value":50000,"currency":"EUR","exponent":null}}},"path":["user"]}],"hasNext":false}
        # -----
        #
        content_str = response.content.decode("utf-8")
        parts = content_str.split("---")
        result = []
        for part in parts:
            if part and part != "--":
                try:
                    json_part = part.split("\r\n\r\n", 1)[-1].strip()
                    data = self.parse_json_garbage(json_part)
                    list_of_accounts = self.list_accounts_from_json(data)
                    result.extend(list_of_accounts)
                except json.JSONDecodeError as e:
                    self.logger.error("Cannot parse json in list account", e)
        return result

    # Extract JSON from a string
    def parse_json_garbage(self, s):
        opening_bracket_index = next((idx for idx, c in enumerate(s) if c in '{['), None)

        if opening_bracket_index is None:
            return None
        s = s[next(idx for idx, c in enumerate(s) if c in '{['):]
        try:
            return json.loads(s)
        except json.JSONDecodeError as e:
            return json.loads(s[:e.pos])

    def list_accounts_from_json(self, json_data):
        result = []
        if json_data is not None:
            accounts = json_data.get('data', {}).get('accounts', [])
            for account in accounts:
                woob_account = Account(id=account['accountRef'])
                amount = account.get('balance', {}).get('amount', {})
                woob_account.currency = amount.get('currency')
                woob_account.balance = amount.get('value') / 100
                woob_account.bank_name = self.BANK_NAME
                woob_account.type = AccountType.CHECKING
                woob_account.label = account['name']
                result.append(woob_account)
            account_wallets = json_data.get('data', {}).get('wallets', {}).get('edges', [])
            for wallet in account_wallets:
                wallet = wallet.get('node', {})
                woob_account = Account(id=wallet['id'])
                amount = wallet.get('balance', {}).get('amount', {})
                woob_account.type = AccountType.DEPOSIT
                woob_account.balance = amount.get('value')
                woob_account.label = f"{wallet['icon']} {wallet['name']}"
                result.append(woob_account)
        return result

    @need_login
    def iter_history(self, account):
        result = []
        hasNextPage = True
        payload = {
            "operationName": "GetTransactionListQueryPagination",
            "query": "query GetTransactionListQueryPagination($first: Int, $after: String, $filter: TransactionsFilter) {\n  transactions(first: $first, after: $after, filter: $filter) {\n    edges {\n      node {\n        id\n        ...TransactionListItemFragment\n        __typename\n      }\n      __typename\n    }\n    pageInfo {\n      startCursor\n      endCursor\n      hasNextPage\n      __typename\n    }\n    __typename\n  }\n}\nfragment TransactionListItemFragment on Transaction {\n  id\n  category\n  counterparty\n  createdAt\n  co2Footprint\n  account {\n    accountRef\n    name\n    __typename\n  }\n  totalRounding {\n    ...AmountFragment\n    __typename\n  }\n  direction\n  status\n  amount {\n    ...AmountFragment\n    __typename\n  }\n  __typename\n}\nfragment AmountFragment on Amount {\n  value\n  currency\n  exponent\n  __typename\n}",
            "variables": {
                "filter": {
                    "statuses": [
                        "AUTHORISED",
                        "COMPLETE",
                    ],
                },
                "first": 50,
            },
        }
        while hasNextPage:
            response = self.do_request(payload)
            hasNextPage = response.get('data', {}).get('transactions', {}).get('pageInfo', {})["hasNextPage"]
            transactions = response.get('data', {}).get('transactions', {}).get('edges', [])
            filtered_transactions = [
                transaction for transaction in transactions
                if transaction['node']['account']['accountRef'] == account.id
            ]
            for transac in filtered_transactions:
                woob_transaction = Transaction(id=transac['node']['id'])
                woob_transaction.amount = transac['node']['amount']['value'] / 100
                woob_transaction.date = datetime.strptime(transac['node']['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ")
                woob_transaction.coming = transac['node']['status'] == 'AUTHORISED'
                woob_transaction.label = transac['node']['counterparty']
                woob_transaction.category = transac['node']['category']
                if transac['node']['direction'] == 'DEBIT':
                    woob_transaction.amount = -woob_transaction.amount
                result.append(woob_transaction)
            payload['variables']['after'] = response.get('data', {}).get('transactions', {}).get('pageInfo', {})["endCursor"]

        return result

    def handle_otp(self):
        pass

    @need_login
    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)
