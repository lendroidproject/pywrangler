# -*- coding: utf-8 -*-

from .utils import get_abi, cmc_rate_per_weth

from datetime import timezone, datetime

from web3 import Web3


class SimpleWrangler:
    """ Base Python class to perform simple operations such as
        1. Undewriting a loan
        2. Liquidating a loan
    """

    def __init__(self, *args, **kwargs):
        self.config = kwargs.get('config', None)
        assert(config is not None)
        self.web3_client = kwargs.get('web3_client', None)
        self.CURRENT_NET =kwargs.get('CURRENT_NET', None)

    def approve_loan(self, loan_request):
        # try:
        data = loan_request
        print(data)
        errors = []
        try:
            assert(data["wrangler"] in ("Lendroid", self.config[self.CURRENT_NET]["wrangler"]))
        except AssertionError as err:
            errors.append({
                'label': 'invalid_wrangler',
                'message': 'Your wrangler is either invalid, or not authorized to approve your loan.'
            })

        # try:
        #     offer_expires_at = datetime_parse(data["offerExpiry"])
        #     now = datetime.now(tz=timezone.utc)
        #     print(offer_expires_at)
        #     print(now)
        #     assert(now < offer_expires_at)
        # except AssertionError as err:
        #     errors.append({
        #         'label': 'order_expired',
        #         'message': 'The order has expired. Please pick another order.'
        #     })
        initial_margin = 1
        weth_dai_rate = float(cmc_rate_per_weth('dai'))
        now = datetime.now(tz=timezone.utc)
        approval_expires_at = now + relativedelta(minutes=2)
        approval_expires_at_timestamp = int((approval_expires_at - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())
        loan_starts_at = approval_expires_at

        loan_duration_seconds = int(data["loanDuration"])
        loan_duration_hours = loan_duration_seconds / 3600
        closing_amount = float(Web3.fromWei(float(data["fillLoanAmount"]), 'ether'))*(1 + (float(Web3.fromWei(float(data["interestRatePerDay"]), 'ether')) * loan_duration_hours) / 2400)
        loan_expires_at = loan_starts_at + relativedelta(hours=loan_duration_hours)
        loan_expires_at_timestamp = int((loan_expires_at - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())
        collateral_amount= float(Web3.fromWei(float(data["fillLoanAmount"]), 'ether')) * weth_dai_rate * initial_margin
        _isOfferCreatorLender = data["lender"] != "0x0000000000000000000000000000000000000000"
        # Set nonce
        wrangler_loan_registry_contract = web3_client.eth.contract(
            address=Web3.toChecksumAddress(self.config[self.CURRENT_NET]["contracts"]["WranglerLoanRegistry"]),
            abi=get_abi('WranglerLoanRegistry'),
        )
        offer_creator = data['lender'] if _isOfferCreatorLender else data['borrower']
        current_nonce = wrangler_loan_registry_contract.functions.nonces(Web3.toChecksumAddress(offer_creator)).call()
        nonce = current_nonce + 1
        loan = {
            'collateralToken': self.config[self.CURRENT_NET]['contracts']['weth'],
            'loanToken': self.config[self.CURRENT_NET]['contracts']['dai'],
            'collateralAmount': Web3.toWei(collateral_amount, 'ether'),
            'loanAmountBorrowed': data["fillLoanAmount"],
            'loanAmountOwed': Web3.toWei(closing_amount, 'ether'),
            'expiresAtTimestamp': loan_expires_at_timestamp,
            'lender': data["lender"] if _isOfferCreatorLender else data["filler"],
            'borrower': data["borrower"] if data["borrower"] != "0x0000000000000000000000000000000000000000" else data["filler"],
            'wrangler': self.config[self.CURRENT_NET]["wrangler"],
            'monitoringFeeLST': data["monitoringFeeLST"],
            'rolloverFeeLST': data["rolloverFeeLST"],
            'closureFeeLST': data["closureFeeLST"],
            'nonce': Web3.toInt(nonce)
        }
        """
            keccak256(
              collateralToken,
              loanToken,
              collateralAmount,
              loanAmountBorrowed,
              loanAmountOwed,
              expiresAtTimestamp,
              lender,
              borrower,
              wrangler,
              monitoringFeeLST,
              rolloverFeeLST,
              closureFeeLST,
              nonce
            )
        """
        loanHash = Web3.soliditySha3(
            [
                'address', 'address',
                'uint256', 'uint256', 'uint256', 'uint256',
                'address', 'address', 'address',
                'uint256', 'uint256', 'uint256', 'uint256'
            ],
            [
                Web3.toChecksumAddress(loan['collateralToken']), Web3.toChecksumAddress(loan['loanToken']),
                Web3.toInt(text=loan['collateralAmount']), Web3.toInt(text=loan['loanAmountBorrowed']), Web3.toInt(text=loan['loanAmountOwed']), Web3.toInt(text=loan['expiresAtTimestamp']),
                Web3.toChecksumAddress(loan['lender']), Web3.toChecksumAddress(loan['borrower']), Web3.toChecksumAddress(loan['wrangler']),
                Web3.toInt(text=loan['monitoringFeeLST']), Web3.toInt(text=loan['rolloverFeeLST']), Web3.toInt(text=loan['closureFeeLST']), loan['nonce']
            ]
        )
        signed_approval = web3_client.eth.account.signHash(loanHash, private_key=Web3.toBytes(hexstr=self.config[self.CURRENT_NET]["private_key"]))
        ec_recover_args = (msghash, v, r, s) = (
            Web3.toHex(signed_approval.messageHash),
            signed_approval.v,
            to_32byte_hex(signed_approval.r),
            to_32byte_hex(signed_approval.s),
        )
        """
            address[7] _addresses,
            // lender, borrower, relayer, wrangler,
            // collateralToken, loanToken,
            // wranglerLoanRegistryContractAddress
        """
        _addresses = [
            loan["lender"],
            loan["borrower"],
            data["relayer"],
            loan['wrangler'],
            loan["collateralToken"],
            loan["loanToken"],
            self.config[self.CURRENT_NET]["contracts"]["WranglerLoanRegistry"]
        ]
        """
            uint[13] _values,
            // collateralAmount,
            // loanAmountOffered, interestRatePerDay, loanDuration, offerExpiryTimestamp,
            // relayerFeeLST, monitoringFeeLST, rolloverFeeLST, closureFeeLST,
            // creatorSalt,
            // wranglerNonce, wranglerApprovalExpiry, loanAmountFilled
        """
        _values = [
            str(Web3.toWei(collateral_amount, 'ether')),
            data["loanAmountOffered"],
            data["interestRatePerDay"],
            str(loan_duration_seconds),
            data["offerExpiry"],
            data["relayerFeeLST"],
            data["monitoringFeeLST"],
            data["rolloverFeeLST"],
            data["closureFeeLST"],
            data["creatorSalt"],
            str(loan["nonce"]),
            str(approval_expires_at_timestamp),
            data["fillLoanAmount"]
        ]
        """
            uint8[2] _vS,
            bytes32[2] _rS,
            bytes32[2] _sS,
            bool _isOfferCreatorLender
        """
        _vS = [
            data["vCreator"],
            signed_approval.v
        ]
        _rS = [
            data["rCreator"],
            to_32byte_hex(signed_approval.r)
        ]
        _sS = [
            data["sCreator"],
            to_32byte_hex(signed_approval.s)
        ]

        approval = {
            "_addresses": _addresses,
            "_values": _values,
            "_vS": _vS,
            "_rS": _rS,
            "_sS": _sS,
            "_isOfferCreatorLender": _isOfferCreatorLender
        }
        print('\n\napproval: {0}'.format(approval))
        return approval, errors
        # except AttributeError as exc:
        #     abort(400, {"error": [str(exc)]})
        # except Exception as exc:
        #     abort(400, {"error": [str(exc)]})
