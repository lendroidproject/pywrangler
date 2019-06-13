# -*- coding: utf-8 -*-

import time
import pprint

from .utils import get_abi, cmc_rate_per_weth, cryptocompare_rate, to_32byte_hex

from datetime import timezone, datetime as dt
from dateutil.relativedelta import relativedelta

from web3 import Web3


def wait_for_receipt(w3, tx_hash, poll_interval):
   while True:
       tx_receipt = w3.eth.getTransactionReceipt(tx_hash)
       if tx_receipt:
         return tx_receipt
       time.sleep(poll_interval)


class LoanRequest:
    """ Base Python class to represent a filled order sent from the relayer UI."""

    def __init__(self, *args, **kwargs):
        self.lender = Web3.toChecksumAddress(kwargs.get('lender', None))
        self.borrower = Web3.toChecksumAddress(kwargs.get('borrower', None))
        self.relayer = Web3.toChecksumAddress(kwargs.get('relayer', None))
        self.wrangler = Web3.toChecksumAddress(kwargs.get('wrangler', None))
        self.filler = Web3.toChecksumAddress(kwargs.get('filler', None))
        self.loanToken = Web3.toChecksumAddress(kwargs.get('loanToken', None))
        self.collateralToken = Web3.toChecksumAddress(kwargs.get('collateralToken', None))
        self.offerExpiry = kwargs.get('offerExpiry', None)
        assert self.offerExpiry is not None
        self.interestRatePerDay = kwargs.get('interestRatePerDay', None)
        assert self.interestRatePerDay is not None
        self.loanDuration = kwargs.get('loanDuration', None)
        assert self.loanDuration is not None
        self.loanAmountOffered = kwargs.get('loanAmountOffered', None)
        assert self.loanAmountOffered is not None
        self.fillLoanAmount = kwargs.get('fillLoanAmount', None)
        assert self.fillLoanAmount is not None
        self.relayerFeeLST = kwargs.get('relayerFeeLST', None)
        assert self.relayerFeeLST is not None
        self.monitoringFeeLST = kwargs.get('monitoringFeeLST', None)
        assert self.monitoringFeeLST is not None
        self.rolloverFeeLST = kwargs.get('rolloverFeeLST', None)
        assert self.rolloverFeeLST is not None
        self.closureFeeLST = kwargs.get('closureFeeLST', None)
        assert self.closureFeeLST is not None
        self.creatorSalt = kwargs.get('creatorSalt', None)
        assert self.creatorSalt is not None
        self.ecSignatureCreator = kwargs.get('ecSignatureCreator', None)
        assert self.ecSignatureCreator is not None


class LoanObject:
    """ Base Python class to represent a loan object."""

    def __init__(self, *args, **kwargs):
        self.lender = Web3.toChecksumAddress(kwargs.get('lender', None))
        self.borrower = Web3.toChecksumAddress(kwargs.get('borrower', None))
        self.relayer = Web3.toChecksumAddress(kwargs.get('relayer', None))
        self.wrangler = Web3.toChecksumAddress(kwargs.get('wrangler', None))
        self.filler = Web3.toChecksumAddress(kwargs.get('filler', None))
        self.loanToken = Web3.toChecksumAddress(kwargs.get('loanToken', None))
        self.collateralToken = Web3.toChecksumAddress(kwargs.get('collateralToken', None))
        self.offerExpiry = kwargs.get('offerExpiry', None)
        assert self.offerExpiry is not None
        self.interestRatePerDay = kwargs.get('interestRatePerDay', None)
        assert self.interestRatePerDay is not None
        self.loanDuration = kwargs.get('loanDuration', None)
        assert self.loanDuration is not None
        self.loanAmountOffered = kwargs.get('loanAmountOffered', None)
        assert self.loanAmountOffered is not None
        self.fillLoanAmount = kwargs.get('fillLoanAmount', None)
        assert self.fillLoanAmount is not None
        self.relayerFeeLST = kwargs.get('relayerFeeLST', None)
        assert self.relayerFeeLST is not None
        self.monitoringFeeLST = kwargs.get('monitoringFeeLST', None)
        assert self.monitoringFeeLST is not None
        self.rolloverFeeLST = kwargs.get('rolloverFeeLST', None)
        assert self.rolloverFeeLST is not None
        self.closureFeeLST = kwargs.get('closureFeeLST', None)
        assert self.closureFeeLST is not None
        self.creatorSalt = kwargs.get('creatorSalt', None)
        assert self.creatorSalt is not None
        self.ecSignatureCreator = kwargs.get('ecSignatureCreator', None)
        assert self.ecSignatureCreator is not None


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
        self.initial_margin = 1.5
        self.loan_request = {}
        self.loan_object = {}
        self.approval = {}

        self.supported_addresses = {Web3.toChecksumAddress(contract_address): contract_name for contract_name, contract_address in self.config[self.CURRENT_NET]["contracts"].items()}
        print('\n\nself.supported_addresses:\n{0}\n\n'.format(self.supported_addresses))

    def current_block_timestamp(self):
        return self.web3_client.eth.getBlock('latest')['timestamp']

    def maker_medianizer_contract(self):
        return self.web3_client.eth.contract(
            address=Web3.toChecksumAddress(self.config[self.CURRENT_NET]["contracts"]["maker_medianizer"]),
            abi=get_abi('MakerMedianizer-{}'.format(self.CURRENT_NET)),
        )

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
        assert len(self.loan_request.__dict__), "self.loan_request needs to be filled"
        try:
            assert self.loan_request.wrangler == Web3.toChecksumAddress(self.config[self.CURRENT_NET]["wrangler"])
        except AssertionError as err:
            self.errors.append({
                'label': 'invalid_wrangler',
                'message': 'Your wrangler is either invalid, or not authorized to approve your loan.'
            })

    def validate_supported_wrangler(self):
        assert len(self.loan_request.__dict__), "self.loan_request needs to be filled"
        try:
            assert self.protocol_contract().functions.wranglers(self.loan_request.wrangler).call()
        except AssertionError as err:
            self.errors.append({
                'label': 'wrangler_not_supported',
                'message': 'The wrangler {0} is not supported.'.format(self.loan_request.wrangler)
            })

    def validate_supported_lend_currency(self):
        assert len(self.loan_request.__dict__), "self.loan_request needs to be filled"
        try:
            assert self.protocol_contract().functions.supported_tokens(self.loan_request.loanToken).call()
        except AssertionError as err:
            self.errors.append({
                'label': 'lend_currency_not_supported',
                'message': 'The lend currency address {0} is not supported.'.format(self.loan_request.loanToken)
            })

    def validate_supported_borrow_currency(self):
        assert len(self.loan_request.__dict__), "self.loan_request needs to be filled"
        try:
            assert self.protocol_contract().functions.supported_tokens(self.loan_request.collateralToken).call()
        except AssertionError as err:
            self.errors.append({
                'label': 'borrow_currency_not_supported',
                'message': 'The borrow currency address {0} is not supported.'.format(self.loan_request.collateralToken)
            })

    def validate_kernel(self):
        assert len(self.loan_request.__dict__), "self.loan_request needs to be filled"
        if self.current_block_timestamp() >= float(self.loan_request.offerExpiry):
            self.errors.append({
                'label': 'kernel_expired',
                'message': 'The order has expired. Please fill another order.'
            })

    def validate_lend_currency_balance(self):
        assert len(self.loan_object), "self.loan_object needs to be filled"
        lend_currency_filled_value = float(Web3.fromWei(float(self.loan_object['loanAmountFilled']), 'ether'))
        try:
            balance = self.ERC20_contract(self.loan_request.loanToken).functions.balanceOf(Web3.toChecksumAddress(self.loan_object['lender'])).call()
            assert float(Web3.fromWei(balance, 'ether')) >= lend_currency_filled_value
        except AssertionError as err:
            self.errors.append({
                'label': 'lend_currency_balance',
                'message': 'Lender does not have enough balance ({0}) of lend currency.'.format(lend_currency_filled_value)
            })

    def validate_lend_currency_allowance(self):
        assert len(self.loan_object), "self.loan_object needs to be filled"
        lend_currency_filled_value = float(Web3.fromWei(float(self.loan_object['loanAmountFilled']), 'ether'))
        try:
            allowance = self.ERC20_contract(self.loan_request.loanToken).functions.allowance(Web3.toChecksumAddress(self.loan_object['lender']), Web3.toChecksumAddress(self.protocol_contract().address)).call()
            assert float(Web3.fromWei(allowance, 'ether')) >= lend_currency_filled_value
        except AssertionError as err:
            self.errors.append({
                'label': 'lend_currency_allowance',
                'message': 'Lender has not set allowance ({0}) for lend currency.'.format(lend_currency_filled_value)
            })

    def validate_borrow_currency_balance(self):
        assert len(self.loan_object), "self.loan_object needs to be filled"
        _borrow_currency_value = self._borrow_currency_value()
        try:
            balance = self.ERC20_contract(self.loan_request.collateralToken).functions.balanceOf(Web3.toChecksumAddress(self.loan_object['borrower'])).call()
            assert float(Web3.fromWei(balance, 'ether')) >= _borrow_currency_value
        except AssertionError as err:
            self.errors.append({
                'label': 'borrow_currency_balance',
                'message': 'Borrower does not have enough balance {0} of borrow currency.'.format(_borrow_currency_value)
            })

    def validate_borrow_currency_allowance(self):
        assert len(self.loan_object), "self.loan_object needs to be filled"
        _borrow_currency_value = self._borrow_currency_value()
        try:
            allowance = self.ERC20_contract(self.loan_request.collateralToken).functions.allowance(Web3.toChecksumAddress(self.loan_object['borrower']), Web3.toChecksumAddress(self.protocol_contract().address)).call()
            assert float(Web3.fromWei(allowance, 'ether')) >= _borrow_currency_value
        except AssertionError as err:
            self.errors.append({
                'label': 'borrow_currency_allowance',
                'message': 'Borrower has not set allowance {0} for borrow currency.'.format(_borrow_currency_value)
            })

    def validate_protocol_currency_balance(self):
        assert len(self.loan_object), "self.loan_object needs to be filled"
        _monitoring_fee = float(Web3.fromWei(float(self.loan_object['monitoringFeeLST']), 'ether'))
        try:
            balance = self.ERC20_contract(self.config[self.CURRENT_NET]['contracts']['lst']).functions.balanceOf(Web3.toChecksumAddress(self.loan_object['lender'])).call()
            assert float(Web3.fromWei(balance, 'ether')) >= _monitoring_fee
        except AssertionError as err:
            self.errors.append({
                'label': 'protocol_currency_allowance_lender',
                'message': 'Lender does not have enough balance {0} of LST.'.format(_monitoring_fee)
            })

    def validate_protocol_currency_allowance(self):
        assert len(self.loan_object), "self.loan_object needs to be filled"
        _monitoring_fee = float(Web3.fromWei(float(self.loan_object['monitoringFeeLST']), 'ether'))
        try:
            allowance = self.ERC20_contract(self.config[self.CURRENT_NET]['contracts']['lst']).functions.allowance(Web3.toChecksumAddress(self.loan_object['lender']), Web3.toChecksumAddress(self.protocol_contract().address)).call()
            assert float(Web3.fromWei(allowance, 'ether')) >= _monitoring_fee
        except AssertionError as err:
            self.errors.append({
                'label': 'protocol_currency_allowance_lender',
                'message': 'Lender has not set allowance {0} for LST.'.format(_monitoring_fee)
            })

    def _owed_value(self):
        return self.protocol_contract().functions.owed_value(
            Web3.toInt(text=self.loan_request.fillLoanAmount),
            Web3.toWei(self.loan_request.interestRatePerDay, "ether"),
            Web3.toInt(text=self.loan_request.loanDuration)
        ).call()

    def _is_kernel_creator_lender(self):
        return self.loan_request.lender != self.ZERO_ADDRESS

    def _kernel_creator(self):
        return self.loan_request.lender if self._is_kernel_creator_lender() else self.loan_request.borrower

    def _weth_dai_rate(self):
        medianizer_rate = float(Web3.fromWei(Web3.toInt(self.maker_medianizer_contract().functions.read().call()), 'ether'))
        if medianizer_rate != 0.0:
            return 1/medianizer_rate
        return float(cmc_rate_per_weth('dai'))

    def _borrow_currency_rate(self):
        if self.supported_addresses[self.loan_request.collateralToken] == 'weth' and self.supported_addresses[self.loan_request.loanToken] == 'dai':
            return self._weth_dai_rate()
        return cryptocompare_rate(
            self.supported_addresses[self.loan_request.loanToken],
            self.supported_addresses[self.loan_request.collateralToken])

    def _borrow_currency_value(self):
        return float(Web3.fromWei(float(self.loan_request.fillLoanAmount), 'ether')) * self._borrow_currency_rate() * self.initial_margin

    def _position_hash_addresses(self):
        return [Web3.toChecksumAddress(self._kernel_creator()), Web3.toChecksumAddress(self.loan_object['lender']), Web3.toChecksumAddress(self.loan_object['borrower']), Web3.toChecksumAddress(self.loan_object['relayer']), Web3.toChecksumAddress(self.loan_object['wrangler']), Web3.toChecksumAddress(self.loan_object['collateralToken']), Web3.toChecksumAddress(self.loan_object['loanToken'])]

    def _position_hash_values(self):
        return [Web3.toInt(text=self.loan_object['collateralAmount']),Web3.toInt(text=self.loan_request.loanAmountOffered),Web3.toInt(text=self.loan_object['relayerFeeLST']),Web3.toInt(text=self.loan_object['monitoringFeeLST']),Web3.toInt(text=self.loan_object['rolloverFeeLST']),Web3.toInt(text=self.loan_object['closureFeeLST']),Web3.toInt(text=self.loan_object['loanAmountFilled'])]

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

    def _sign_fill_kernel_transaction(self):
        assert len(self.approval), "self.approval needs to be filled"
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

        chain_id = 0
        if self.CURRENT_NET == 'mainnet':
            chain_id = 1
        elif self.CURRENT_NET == 'kovan':
            chain_id = 42
        else:
            chain_id = 101
        assert chain_id > 0, "invalid chain id {0}".format(chain_id)

        signed_raw_tx_bytes = self.web3_client.eth.account.signTransaction(
            self.protocol_contract().functions.fill_kernel(
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
            ).buildTransaction({
                'chainId': chain_id,
                'gas': gas_estimate,
                'gasPrice': self.web3_client.eth.gasPrice,
                'nonce': self.web3_client.eth.getTransactionCount(Web3.toChecksumAddress(self.config[self.CURRENT_NET]["wrangler"])),
            }),
            private_key=Web3.toBytes(hexstr=self.config[self.CURRENT_NET]["private_key"])
        ).rawTransaction
        signed_raw_tx_hex = Web3.toHex(signed_raw_tx_bytes)

        return gas_estimate, signed_raw_tx_hex

    def create_loan_object(self):
        current_nonce = self.protocol_contract().functions.wrangler_nonces(self.loan_request.wrangler, Web3.toChecksumAddress(self._kernel_creator())).call()
        nonce = current_nonce + 1
        lending_currency_owed_value = self._owed_value()
        self.loan_object = {
            'collateralToken': self.loan_request.collateralToken,
            'loanToken': self.loan_request.loanToken,
            'collateralAmount': Web3.toWei(self._borrow_currency_value(), 'ether'),
            'loanAmountFilled': self.loan_request.fillLoanAmount,
            'loanAmountOwed': lending_currency_owed_value,
            'expiresAtTimestamp': self.current_block_timestamp() + int(self.loan_request.loanDuration),
            'lender': self.loan_request.lender if self._is_kernel_creator_lender() else self.loan_request.filler,
            'borrower': self.loan_request.borrower if self.loan_request.borrower != self.ZERO_ADDRESS else self.loan_request.filler,
            "relayer": self.loan_request.relayer,
            "wrangler": self.loan_request.wrangler,
            'relayerFeeLST': self.loan_request.relayerFeeLST,
            'monitoringFeeLST': self.loan_request.monitoringFeeLST,
            'rolloverFeeLST': self.loan_request.rolloverFeeLST,
            'closureFeeLST': self.loan_request.closureFeeLST,
            'nonce': Web3.toInt(nonce)
        }

    def create_approval(self):
        _addresses = [
            self.loan_object['lender'],
            self.loan_object['borrower'],
            self.loan_request.relayer,
            self.loan_object['wrangler'],
            self.loan_object['collateralToken'],
            self.loan_object['loanToken']
        ]
        _values = [
            str(Web3.toWei(self._borrow_currency_value(), 'ether')),
            self.loan_request.loanAmountOffered,
            self.loan_request.relayerFeeLST,
            self.loan_request.monitoringFeeLST,
            self.loan_request.rolloverFeeLST,
            self.loan_request.closureFeeLST,
            self.loan_request.fillLoanAmount
        ]
        _timestamps = [
            self.loan_request.offerExpiry,
            str(self.current_block_timestamp() + (2 * 60))
        ]


        self.approval = {
            "_addresses": [Web3.toChecksumAddress(self.loan_object['lender']),Web3.toChecksumAddress(self.loan_object['borrower']),Web3.toChecksumAddress(self.loan_object['relayer']),Web3.toChecksumAddress(self.loan_object['wrangler']),Web3.toChecksumAddress(self.loan_object['collateralToken']),Web3.toChecksumAddress(self.loan_object['loanToken'])],
            "_values": self._position_hash_values(),
            "_nonce": Web3.toInt(text=self.loan_object['nonce']),
            "_kernel_daily_interest_rate": Web3.toWei(self.loan_request.interestRatePerDay, "ether"),
            "_is_creator_lender": self._is_kernel_creator_lender(),
            "_timestamps": [Web3.toInt(text=_timestamp) for _timestamp in _timestamps],
            "_position_duration_in_seconds": Web3.toInt(text=self.loan_request.loanDuration),
            "_kernel_creator_salt": self.loan_request.creatorSalt,
            "_sig_data_kernel_creator": self.loan_request.ecSignatureCreator,
            "_sig_data_wrangler": Web3.toHex(self._signed_approval())
        }

    def approve_loan(self, data):
        self.loan_request = LoanRequest(**data)
        # reset parameters
        self.errors = []
        self.loan_object = {}
        self.approval = {}
        # perform validations
        self.validate_wrangler()
        self.validate_supported_wrangler()
        self.validate_supported_lend_currency()
        self.validate_supported_borrow_currency()
        self.validate_kernel()
        # create loan object
        self.create_loan_object()
        # perform some more validations
        self.validate_lend_currency_balance()
        self.validate_lend_currency_allowance()
        self.validate_borrow_currency_balance()
        self.validate_borrow_currency_allowance()
        self.validate_protocol_currency_balance()
        self.validate_protocol_currency_allowance()
        # create approval
        self.create_approval()

        if not len(self.errors):
            # estimate gas cost for transaction
            try:
                gas_estimate, signed_tx = self._sign_fill_kernel_transaction()
                print("Gas estimate to transact with fill_kernel: {0}\n".format(gas_estimate))
                self.approval["_gas_estimate"] = gas_estimate
                self.approval["_signed_transaction"] = signed_tx
            except ValueError as err:
                self.errors.append({
                    'label': 'invalid_paramaters',
                    'message': """{0}""".format(err)
                })

        self.loan_object['loanAmountOwed'] = str(self.loan_object['loanAmountOwed'])

        return self.loan_object, self.approval, self.errors

    def get_positions(self, _address=None):
        positions = []
        _address = _address or None
        if not _address:
            last_position_index = self.protocol_contract().functions.last_position_index().call()
            while last_position_index > -1:
                position_hash = self.protocol_contract().functions.position_index(last_position_index).call()
                position = self.protocol_contract().functions.position(position_hash).call()
                positions.append(position)
                last_position_index -= 1
        return positions

    def liquidate(self, position_hash):
        assert position_hash is not None, "position_hash cannot be None"
        print("Sending transaction to liquidate_position : {0}\n".format(position_hash))
        chain_id = 0
        if self.CURRENT_NET == 'mainnet':
            chain_id = 1
        elif self.CURRENT_NET == 'kovan':
            chain_id = 42
        else:
            chain_id = 101
        assert chain_id > 0, "invalid chain id {0}".format(chain_id)
        tx_nonce = self.web3_client.eth.getTransactionCount(Web3.toChecksumAddress(self.config[self.CURRENT_NET]["wrangler"]))
        liquidate_txn = self.protocol_contract().functions.liquidate_position(position_hash).buildTransaction({
            'chainId': chain_id,
            'gas': 1150000,
            'gasPrice': self.web3_client.eth.gasPrice,
            'nonce': tx_nonce,
        })
        signed_txn = self.web3_client.eth.account.signTransaction(liquidate_txn, private_key=Web3.toBytes(hexstr=self.config[self.CURRENT_NET]["private_key"]))
        tx_hash = self.web3_client.eth.sendRawTransaction(signed_txn.rawTransaction)
        receipt = wait_for_receipt(self.web3_client, tx_hash, 1)
        print("Transaction receipt mined: \n")
        pprint.pprint(dict(receipt))

        return True


    def monitor(self):
        # iterate over each position
        for position in self.get_positions():
            # check if the position has expired and is still open
            if (self.current_block_timestamp() >= position[8]) and (position[15] == 1):
                # liquidate the position
                self.liquidate(position[21])

    def get_loan_health(self, position_index):
        health = 0
        self.errors = []
        if position_index < 0:
            self.errors.append({
                'label': 'invalid_position_index',
                'message': 'Loan position index cannot be negative'
            })
        # get the position
        position_hash = self.protocol_contract().functions.position_index(Web3.toInt(text=position_index)).call()
        position = self.protocol_contract().functions.position(position_hash).call()
        borrow_currency_address = Web3.toChecksumAddress(position[9])
        lend_currency_address = Web3.toChecksumAddress(position[10])
        initial_collateral_amount = float(Web3.fromWei(float(position[11]), 'ether'))
        lend_currency_filled = float(Web3.fromWei(float(position[13]), 'ether'))

        lend_currency_current_rate_per_borrow_currency = cryptocompare_rate(
            self.supported_addresses[borrow_currency_address],
            self.supported_addresses[lend_currency_address]
        )

        health = initial_collateral_amount * lend_currency_current_rate_per_borrow_currency * 100 / self.initial_margin / lend_currency_filled

        return health, self.errors
