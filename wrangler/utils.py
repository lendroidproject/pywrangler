import json
import requests

from web3 import Web3


def get_json_data_from_file(filename):
    data = None
    with open(filename) as json_data_file:
        data = json.load(json_data_file)
    assert(data is not None)
    return data


def get_abi(contract=None):
    contract = contract or None
    assert(contract is not None)
    filename = "./abis/{0}.json".format(contract)
    return get_json_data_from_file(filename)


def cmc_rate_per_weth(ticker):
    cmc_api_url = "https://api.coinmarketcap.com/v1/ticker/{0}/?convert=ETH".format(ticker)
    return requests.get(cmc_api_url).json()[0]["price_eth"]


def to_32byte_hex(val):
    return Web3.toHex(Web3.toBytes(val).rjust(32, b'\0'))
