# -*- coding: utf-8 -*-

import json
import requests

from flask import Flask, render_template, request, jsonify, abort
from flask_restplus import Resource, Api
from flask_cors import CORS

from web3 import Web3

from wrangler import get_json_data_from_file, SimpleWrangler as Wrangler


config = get_json_data_from_file("./secret.json")
DEV = True
CURRENT_NET = 'kovan' if DEV else 'mainnet'
HTTP_PROVIDER_URI = "https://{0}.infura.io/v3/{1}".format(CURRENT_NET, config[CURRENT_NET]['infura_key'])
LOCAL = False
if LOCAL:
    CURRENT_NET = 'local'
    HTTP_PROVIDER_URI = 'http://localhost:8545'

w3 = Web3(Web3.HTTPProvider(HTTP_PROVIDER_URI))
app = Flask(__name__)

# Add CORS support for all domains
CORS(
    app, origins="*",
    allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
    supports_credentials=True
)

# Add support for Restplus api
api = Api(app)


# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Return a custom 404 error."""
    return 'Sorry, nothing at this URL.', 404


# api endpoints
@api.route('/loan_requests', endpoint='loan_requests')
class LoanRequests(Resource):

    def post(self):
        """ Approve a loan request."""
        w = Wrangler(
            config=config,
            web3_client=w3,
            current_net=CURRENT_NET
        )
        loan, approval, errors = w.approve_loan(request.get_json(force=True))
        if len(errors):
            abort(400, {"error": errors})

        return { 'data': loan, 'approval': approval }, 201


@api.route('/loan_health/<int:position_index>', endpoint='loan_health')
class LoanHealth(Resource):

    def get(self, position_index):
        """ Return the health of the collateral for a loan, given its loan number."""
        w = Wrangler(
            config=config,
            web3_client=w3,
            current_net=CURRENT_NET
        )
        health, errors = w.get_loan_health(position_index)
        if len(errors):
            abort(400, {"error": errors})

        return { 'data': health }, 201


@api.route('/is_valid_protocol_transaction_sender/<string:prover>/<string:txHash>', endpoint='is_valid_protocol_transaction_sender')
class LoanHealth(Resource):

    def get(self, prover, txHash):
        """ Return the health of the collateral for a loan, given its loan number."""
        w = Wrangler(
            config=config,
            web3_client=w3,
            current_net=CURRENT_NET
        )

        is_valid_sender = w.is_valid_protocol_transaction_sender(prover, txHash)
        print('\n\nis_valid_sender: {0}\n\n'.format(is_valid_sender))
        if not is_valid_sender:
            abort(400)

        return {}, 200


if __name__ == '__main__':
    app.run(debug=True)
