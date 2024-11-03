from woob.capabilities.bank import (
    CapBank, Account, Transaction,
    AccountNotFound
)

from woob.browser.browsers import Browser, StatesMixin

from woob.browser.mfa import TwoFactorBrowser

from woob.browser.browsers import need_login
from woob.browser.url import URL
from woob.capabilities.base import find_object

from .pages import SendOTPCodePage, GetTokenPage, GetAccountPage, GetTransactionsPage

from woob.exceptions import (
    AppValidation, AppValidationCancelled, AppValidationExpired, BrowserIncorrectPassword,
    BrowserUnavailable, BrowserUserBanned, OTPSentType, SentOTPQuestion,
)

import json
from datetime import datetime


class GreenGotBrowser(TwoFactorBrowser, StatesMixin):
    BASEURL = ''

    BANK_NAME = 'GreenGot'

    send_otp_code = URL(r'/graphql', SendOTPCodePage)
    get_token_page = URL(r'/graphql', GetTokenPage)
    get_account_page = URL(r'/graphql', GetAccountPage)
    get_transactions_page = URL(r'graphql', GetTransactionsPage)

    def __init__(self, config, email, *args, **kwargs):
        super(GreenGotBrowser, self).__init__(config, email, "", *args, **kwargs)
        self.email = email
        self.BASEURL = 'https://api.retail.green-got.com/graphql'

        self.AUTHENTICATION_METHODS = {
            'smscode': self.handle_otp,
            'emailcode': self.handle_otp,
        }
        self.access_token = None
        self.__states__ = (
            'access_token',
        )

    def deinit(self):
        return super(GreenGotBrowser, self).deinit()
    
    def do_login(self):
        if(self.access_token == None):
            if(self.config["smscode"].get() == None):
                payload = {
                    "operationName": "UserSignInMutation",
                    "query": "mutation UserSignInMutation($input: SignInInput!) {\n  user_signIn(input: $input) {\n    __typename\n    ... on LoginCodeJustSent {\n      signInMethod\n      __typename\n    }\n    ... on SignInSuccess {\n      signInMethod\n      __typename\n    }\n  }\n}",
                    "variables": {
                        "input": {
                        "email": self.email
                        }
                    }
                }
                headers = {}
                self.send_otp_code.go(json=payload, headers=headers)
                raise SentOTPQuestion(
                    'smscode',
                    medium_type=OTPSentType.SMS,
                    message='Veuillez entrer le code reçu par SMS',
                )
            elif(self.config["emailcode"].get() == None):
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
                "smsCode": self.config["smscode"].get()
                }
            }
        }
        headers = {}
        response = self.get_token_page.go(json=payload, headers=headers)
        try:
            data = response.json()
        except Exception:
            data = None
        self.access_token = data["data"]["user_checkLoginCode"]["idToken"]

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})

        if self.access_token != None:
            headers['Authorization'] = 'Bearer %s' % self.access_token

        headers['Accept'] = 'application/graphql-response+json, application/graphql+json, application/json, text/event-stream, multipart/mixed'

        req = super(GreenGotBrowser, self).build_request(*args, **kwargs)
        return req
    
    def raise_for_status(self, response):
        if '"code":"UNAUTHORIZED' in response.content.decode("utf-8"):
            self.access_token = None
        return super(GreenGotBrowser, self).raise_for_status(response)


    @need_login
    def iter_accounts(self):
        payload = {
            "operationName": "AccountsScreenQuery",
            "query": "query AccountsScreenQuery {\n  ...Savings\n  ...Suggestions\n  ...KYCStatus\n  wallets {\n    edges {\n      node {\n        ...WalletListCardFields\n        __typename\n      }\n      __typename\n    }\n    pageInfo {\n      startCursor\n      endCursor\n      hasNextPage\n      __typename\n    }\n    __typename\n  }\n  user: user_v2 {\n    id\n    ...Balance\n    __typename\n  }\n  accounts {\n    accountRef\n    __typename\n  }\n  ...AccountListCardFragment\n}\nfragment KYCStatus on Query {\n  completedOnboardings: onboardings(filter: {statuses: [COMPLETED]}) {\n    id\n    topUpAmount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  user: user_v2 {\n    id\n    verification {\n      status\n      __typename\n    }\n    firstName\n    __typename\n  }\n  __typename\n}\nfragment AmountFragment on Amount {\n  value\n  currency\n  exponent\n  __typename\n}\nfragment Balance on User_v2 {\n  ... on User_v2 @defer {\n    balance {\n      amount {\n        ...AmountFragment\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment AccountListCardFragment on Query {\n  accounts {\n    __typename\n    accountRef\n    ...AccountFields\n    balance {\n      amount {\n        ...AmountFragment\n        __typename\n      }\n      __typename\n    }\n  }\n  completedOnboardings: onboardings(filter: {statuses: [COMPLETED]}) {\n    __typename\n    id\n    ...OnboardingFields\n    topUpAmount {\n      ...AmountFragment\n      __typename\n    }\n  }\n  __typename\n}\nfragment OnboardingFields on Onboarding {\n  id\n  name\n  icon\n  topUpAmount {\n    ...AmountFragment\n    __typename\n  }\n  __typename\n}\nfragment AccountFields on Account {\n  name\n  accountRef\n  cards(filter: {latest: true}) {\n    design\n    designSymbol\n    __typename\n  }\n  balance {\n    amount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment WalletListCardFields on Wallet {\n  ...WalletFields\n  balance {\n    amount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment WalletFields on Wallet {\n  id\n  name\n  icon\n  balance {\n    amount {\n      ...AmountFragment\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\nfragment Suggestions on Query {\n  accounts {\n    accountRef\n    __typename\n  }\n  user: user_v2 {\n    id\n    productSuggestions\n    __typename\n  }\n  __typename\n}\nfragment Savings on Query {\n  investments: investments_v2 {\n    __typename\n    status\n    subscriptionId\n    ...ContractFields\n  }\n  investmentSubscription {\n    subscriptionId\n    status\n    ...SubscriptionFields\n    __typename\n  }\n  __typename\n}\nfragment ContractFields on InvestmentContract {\n  subscriptionId\n  ... @defer {\n    details: detailsV2 {\n      __typename\n      ... on InvestmentDetails {\n        amount {\n          ...AmountFragment\n          __typename\n        }\n        __typename\n      }\n    }\n    __typename\n  }\n  __typename\n}\nfragment SubscriptionFields on InvestmentSubscription_v2 {\n  subscriptionId\n  status\n  __typename\n}"
        }
        response = self.get_account_page.go(json=payload)
        
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
                    print("Erreur de décodage JSON dans une partie multipart:", e)
        return result
    
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
                woob_account.balance = amount.get('value')
                woob_account.bank_name = self.BANK_NAME
                woob_account.label = account['name']
                result.append(woob_account)
        return result

    @need_login
    def iter_history(self, account):
        result = []
        payload = {
            "operationName": "GetTransactionListQueryPagination",
            "query": "query GetTransactionListQueryPagination($first: Int, $after: String, $filter: TransactionsFilter) {\n  transactions(first: $first, after: $after, filter: $filter) {\n    edges {\n      node {\n        id\n        ...TransactionListItemFragment\n        __typename\n      }\n      __typename\n    }\n    pageInfo {\n      startCursor\n      endCursor\n      hasNextPage\n      __typename\n    }\n    __typename\n  }\n}\nfragment TransactionListItemFragment on Transaction {\n  id\n  category\n  counterparty\n  createdAt\n  co2Footprint\n  account {\n    accountRef\n    name\n    __typename\n  }\n  totalRounding {\n    ...AmountFragment\n    __typename\n  }\n  direction\n  status\n  amount {\n    ...AmountFragment\n    __typename\n  }\n  __typename\n}\nfragment AmountFragment on Amount {\n  value\n  currency\n  exponent\n  __typename\n}",
            "variables": {
                "filter": {
                    "statuses": [
                    "AUTHORISED",
                    "COMPLETE"
                    ]
                },
                "first": 20
            }
        }
        response = self.get_transactions_page.go(json=payload)
        transactions = response.json().get('data', {}).get('transactions', {}).get('edges', [])
        filtered_transactions = [
            transaction for transaction in transactions
            if transaction['node']['account']['accountRef'] == account.id
        ]
        for transac in filtered_transactions:
            woob_transaction = Transaction(id=transac['node']['id'])
            woob_transaction.amount = transac['node']['amount']['value'] / 100
            woob_transaction.date = date_obj = datetime.strptime(transac['node']['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ")
            woob_transaction.coming = transac['node']['status'] == 'AUTHORISED'
            woob_transaction.label = transac['node']['counterparty']
            woob_transaction.category = transac['node']['category']
            if transac['node']['direction'] == 'DEBIT':
                woob_transaction.amount = -woob_transaction.amount
            result.append(woob_transaction)
        return result


    def handle_otp(self):
        pass

    @need_login
    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)