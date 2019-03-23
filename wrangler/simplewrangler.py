# -*- coding: utf-8 -*-

import time
import pprint

from .utils import get_abi, cmc_rate_per_weth, to_32byte_hex

from datetime import timezone, datetime
from dateutil.relativedelta import relativedelta

from web3 import Web3


def wait_for_receipt(w3, tx_hash, poll_interval):
   while True:
       tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
       if tx_receipt:
         return tx_receipt
       time.sleep(poll_interval)


class SimpleWrangler:
    """ Base Python class to perform simple operations such as
        1. Approving a loan request
        2. Liquidating a loan (WIP)
    """

    def __init__(self, *args, **kwargs):
        self.config = kwargs.get('config', None)
        assert(self.config is not None)
        self.web3_client = kwargs.get('web3_client', None)
        assert(self.web3_client is not None)
        self.CURRENT_NET =kwargs.get('current_net', None)
        assert(self.CURRENT_NET is not None)

        self.ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
        self.errors = []
        self.initial_margin = 1
        self.loan_request = {}
        self.loan_object = {}
        self.approval = {}

    def protocol_contract(self):
        return self.web3_client.eth.contract(
            address=Web3.toChecksumAddress(self.config[self.CURRENT_NET]["contracts"]["protocol"]),
            abi=get_abi('protocol'),
        )

    def ERC20_contract(self, _address):
        return self.web3_client.eth.contract(
            address=Web3.toChecksumAddress(_address),
            abi=get_abi('ERC20'),
        )

    def validate_wrangler(self):
        try:
            assert(Web3.toChecksumAddress(self.loan_request["wrangler"]) in ("Lendroid", Web3.toChecksumAddress(self.config[self.CURRENT_NET]["wrangler"])))
        except AssertionError as err:
            self.errors.append({
                'label': 'invalid_wrangler',
                'message': 'Your wrangler is either invalid, or not authorized to approve your loan.'
            })

    def validate_supported_wrangler(self):
        try:
            assert self.protocol_contract().functions.wranglers(Web3.toChecksumAddress(self.loan_request["wrangler"])).call()
        except AssertionError as err:
            self.errors.append({
                'label': 'wrangler_not_supported',
                'message': 'The wrangler {0} is not supported.'.format(Web3.toChecksumAddress(self.loan_request["wrangler"]))
            })

    def validate_supported_lend_currency(self):
        try:
            assert self.protocol_contract().functions.supported_tokens(Web3.toChecksumAddress(self.config[self.CURRENT_NET]['contracts']['dai'])).call()
        except AssertionError as err:
            self.errors.append({
                'label': 'lend_currency_not_supported',
                'message': 'The lend currency is not supported.'
            })

    def owed_value(self):
        return self.protocol_contract().functions.owed_value(
            Web3.toInt(text=self.loan_request["fillLoanAmount"]),
            Web3.toWei(self.loan_request["interestRatePerDay"], "ether"),
            Web3.toInt(text=self.loan_request["loanDuration"])
        ).call()


    def validate_supported_borrow_currency(self):
        try:
            assert self.protocol_contract().functions.supported_tokens(Web3.toChecksumAddress(self.config[self.CURRENT_NET]['contracts']['weth'])).call()
        except AssertionError as err:
            self.errors.append({
                'label': 'borrow_currency_not_supported',
                'message': 'The borrow currency is not supported.'
            })

    def validate_lend_currency_allowance(self):
        try:
            allowance = self.ERC20_contract(self.config[self.CURRENT_NET]['contracts']['dai']).functions.allowance(Web3.toChecksumAddress(self.loan_object["lender"]), Web3.toChecksumAddress(self.protocol_contract().address)).call()
            assert float(Web3.fromWei(allowance, 'ether')) >= float(Web3.fromWei(float(self.loan_object["loanAmountFilled"]), 'ether'))
        except AssertionError as err:
            self.errors.append({
                'label': 'lend_currency_allowance',
                'message': 'Lender has not set allowance for Lend currency.'
            })

    def validate_borrow_currency_allowance(self):
        try:
            allowance = self.ERC20_contract(self.config[self.CURRENT_NET]['contracts']['weth']).functions.allowance(Web3.toChecksumAddress(self.loan_object["borrower"]), Web3.toChecksumAddress(self.protocol_contract().address)).call()
            assert float(Web3.fromWei(allowance, 'ether')) >= self._borrow_currency_value()
        except AssertionError as err:
            self.errors.append({
                'label': 'borrow_currency_allowance',
                'message': 'Borrower has not set allowance for Borrow currency.'
            })

    def validate_protocol_currency_allowance(self):
        try:
            allowance = self.ERC20_contract(self.config[self.CURRENT_NET]['contracts']['lst']).functions.allowance(Web3.toChecksumAddress(self.loan_object["lender"]), Web3.toChecksumAddress(self.protocol_contract().address)).call()
            assert float(Web3.fromWei(allowance, 'ether')) >= float(Web3.fromWei(float(self.loan_object["monitoringFeeLST"]), 'ether'))
        except AssertionError as err:
            self.errors.append({
                'label': 'protocol_currency_allowance_lender',
                'message': 'Lender has not set allowance for LST.'
            })

    def _is_kernel_creator_lender(self):
        return self.loan_request["lender"] != self.ZERO_ADDRESS

    def _kernel_creator(self):
        return self.loan_request['lender'] if self._is_kernel_creator_lender() else self.loan_request['borrower']

    def _weth_dai_rate(self):
        return float(cmc_rate_per_weth('dai'))

    def _approval_expiry(self, timestamp=False):
        timestamp = timestamp or False
        now = datetime.now(tz=timezone.utc)
        approval_expires_at = now + relativedelta(minutes=2)
        if not timestamp:
            return approval_expires_at
        return int((approval_expires_at - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())

    def _borrow_currency_value(self):
        return float(Web3.fromWei(float(self.loan_request["fillLoanAmount"]), 'ether')) * self._weth_dai_rate() * self.initial_margin

    def _position_hash_addresses(self):
        return [Web3.toChecksumAddress(self._kernel_creator()), Web3.toChecksumAddress(self.loan_object['lender']), Web3.toChecksumAddress(self.loan_object['borrower']), Web3.toChecksumAddress(self.loan_object['relayer']), Web3.toChecksumAddress(self.loan_object['wrangler']), Web3.toChecksumAddress(self.loan_object['collateralToken']), Web3.toChecksumAddress(self.loan_object['loanToken'])]

    def _position_hash_values(self):
        return [Web3.toInt(text=self.loan_object['collateralAmount']), Web3.toInt(text=self.loan_request['loanAmountOffered']), Web3.toInt(text=self.loan_object['relayerFeeLST']), Web3.toInt(text=self.loan_object['monitoringFeeLST']), Web3.toInt(text=self.loan_object['rolloverFeeLST']), Web3.toInt(text=self.loan_object['closureFeeLST']), Web3.toInt(text=self.loan_object['loanAmountFilled'])]

    def _signed_approval(self):
        position_hash = self.protocol_contract().functions.position_hash(
            self._position_hash_addresses(),
            self._position_hash_values(),
            self.loan_object['loanAmountOwed'],
            Web3.toInt(text=self.loan_object['nonce'])
        ).call()

        position_hash = Web3.soliditySha3(['bytes32', 'bytes32'], [Web3.toBytes(text='\x19Ethereum Signed Message:\n32'), position_hash])
        _signature = self.web3_client.eth.account.signHash(position_hash, private_key=Web3.toBytes(hexstr=self.config[self.CURRENT_NET]["private_key"]))
        return _signature.signature

    def create_loan_object(self):
        current_nonce = self.protocol_contract().functions.wrangler_nonces(Web3.toChecksumAddress(self.loan_request["wrangler"]), Web3.toChecksumAddress(self._kernel_creator())).call()
        nonce = current_nonce + 1
        loan_starts_at = self._approval_expiry()
        loan_duration_seconds = int(self.loan_request["loanDuration"])
        loan_duration_hours = loan_duration_seconds / 3600
        # loan_duration_days = loan_duration_seconds / 86400
        # total_interest = float(self.loan_request["interestRatePerDay"]) * 0.01 * loan_duration_days
        # principal = float(Web3.fromWei(float(self.loan_request["fillLoanAmount"]), 'ether'))
        # amount = principal*(1 + total_interest)
        lending_currency_owed_value = self.owed_value()
        # print('\n\nprincipal: {0}'.format(principal))
        # print('\n\namount: {0}'.format(amount))
        # print('\n\nlending_currency_owed_value: {0}'.format(lending_currency_owed_value))
        loan_expires_at = loan_starts_at + relativedelta(hours=loan_duration_hours)
        loan_expires_at_timestamp = int((loan_expires_at - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())
        self.loan_object = {
            'collateralToken': self.config[self.CURRENT_NET]['contracts']['weth'],
            'loanToken': self.config[self.CURRENT_NET]['contracts']['dai'],
            'collateralAmount': Web3.toWei(self._borrow_currency_value(), 'ether'),
            'loanAmountFilled': self.loan_request["fillLoanAmount"],
            'loanAmountOwed': lending_currency_owed_value,
            'expiresAtTimestamp': loan_expires_at_timestamp,
            'lender': self.loan_request["lender"] if self._is_kernel_creator_lender() else self.loan_request["filler"],
            'borrower': self.loan_request["borrower"] if self.loan_request["borrower"] != self.ZERO_ADDRESS else self.loan_request["filler"],
            "relayer": self.loan_request["relayer"],
            "wrangler": self.loan_request["wrangler"],
            'relayerFeeLST': self.loan_request["relayerFeeLST"],
            'monitoringFeeLST': self.loan_request["monitoringFeeLST"],
            'rolloverFeeLST': self.loan_request["rolloverFeeLST"],
            'closureFeeLST': self.loan_request["closureFeeLST"],
            'nonce': Web3.toInt(nonce)
        }
        # print('\n\nself.loan_object: {0}'.format(self.loan_object))

    def create_approval(self):
        _addresses = [
            self.loan_object["lender"],
            self.loan_object["borrower"],
            self.loan_request["relayer"],
            self.loan_object['wrangler'],
            self.loan_object["collateralToken"],
            self.loan_object["loanToken"]
        ]
        _values = [
            str(Web3.toWei(self._borrow_currency_value(), 'ether')),
            self.loan_request["loanAmountOffered"],
            self.loan_request["relayerFeeLST"],
            self.loan_request["monitoringFeeLST"],
            self.loan_request["rolloverFeeLST"],
            self.loan_request["closureFeeLST"],
            self.loan_request["fillLoanAmount"]
        ]
        _timestamps = [
            self.loan_request["offerExpiry"],
            str(self._approval_expiry(timestamp=True))
        ]

        self.approval = {
            "_addresses": [Web3.toChecksumAddress(self.loan_object['lender']), Web3.toChecksumAddress(self.loan_object['borrower']), Web3.toChecksumAddress(self.loan_object['relayer']), Web3.toChecksumAddress(self.loan_object['wrangler']), Web3.toChecksumAddress(self.loan_object['collateralToken']), Web3.toChecksumAddress(self.loan_object['loanToken'])],
            "_values": self._position_hash_values(),
            "_nonce": Web3.toInt(text=self.loan_object['nonce']),
            # "_kernel_daily_interest_rate": Web3.toInt(text=self.loan_request["interestRatePerDay"]),
            "_kernel_daily_interest_rate": Web3.toWei(self.loan_request["interestRatePerDay"], "ether"),
            "_is_creator_lender": self._is_kernel_creator_lender(),
            "_timestamps": [Web3.toInt(text=_timestamp) for _timestamp in _timestamps],
            "_position_duration_in_seconds": Web3.toInt(text=self.loan_request["loanDuration"]),
            "_kernel_creator_salt": self.loan_request["creatorSalt"],
            "_sig_data_kernel_creator": self.loan_request["ecSignatureCreator"],
            "_sig_data_wrangler": Web3.toHex(self._signed_approval())
        }
        # print('\n\nself.approval: {0}'.format(self.approval))

    def approve_loan(self, data):
        self.loan_request = data
        # print(self.loan_request)
        self.errors = []
        self.validate_wrangler()
        self.validate_supported_wrangler()
        self.validate_supported_lend_currency()
        self.validate_supported_borrow_currency()

        self.create_loan_object()

        self.validate_lend_currency_allowance()
        self.validate_borrow_currency_allowance()
        self.validate_protocol_currency_allowance()

        self.create_approval()

        # print('\n\nprotocol_contract : {0}'.format(self.protocol_contract().address))

        if not len(self.errors):
            try:
                gas_estimate = self.protocol_contract().functions.fill_kernel(
                    self.approval['_addresses'],
                    self.approval['_values'],
                    self.approval['_nonce'],
                    self.approval['_kernel_daily_interest_rate'],
                    self.approval['_is_creator_lender'],
                    self.approval['_timestamps'],
                    self.approval['_position_duration_in_seconds'],
                    self.approval['_kernel_creator_salt'],
                    self.approval['_sig_data_kernel_creator'],
                    self.approval['_sig_data_wrangler']
                ).estimateGas()
                print("Gas estimate to transact with fill_kernel: {0}\n".format(gas_estimate))
            except ValueError as err:
                self.errors.append({
                    'label': 'invalid_paramaters',
                    'message': """{0}""".format(err)
                })

        return self.loan_object, self.approval, self.errors

    def get_positions(self, _address=None):
        positions = []
        _address = _address or None
        if _address:
            _address = Web3.toChecksumAddress(_address)
            last_nonce = self.protocol_contract().functions.wrangler_nonces(Web3.toChecksumAddress(self.config[self.CURRENT_NET]["wrangler"]), _address).call()
        return positions


    def monitor(self):
        positions = self.get_positions()
