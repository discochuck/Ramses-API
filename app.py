import json

import requests
from flask import Flask, jsonify, request
from flask_caching import Cache
from flask_cors import CORS

from claimable_rewards import get_voter_claimable_rewards
from fetch_voted_pairs import check_balance
from get_apr import get_apr, get_pairs
from utils import db, cache_config

app = Flask(__name__)

CORS(app)
cache = Cache(app, config=cache_config)


@app.route("/")
@cache.cached(60 * 60)
def apr():
    try:
        apr = get_apr()
        # todo notify admin
    except:
        apr = json.loads(db.get('apr'))

    return jsonify(apr)


@app.route("/pairs")
@cache.cached(5 * 60)
def pairs():
    print('function call')
    return jsonify(get_pairs())


@app.route("/voterClaimableRewards")
def voter_claimable_rewards():
    token_id = request.args.get('token_id')
    return jsonify(
        get_voter_claimable_rewards(int(token_id))
    )


@app.route("/db")
def fetch_from_db():
    key = request.args.get('key')
    return jsonify(
        json.loads(db.get(key))
    )


@app.route("/check_rewards/<pair_address>")
def check_rewards(pair_address):
    pair = json.loads(db.get('pairs'))[pair_address]

    fee_distributor_address = pair['fee_distributor_address']

    result = []
    for token in pair['fee_distributor_tokens']:
        missing_amount = -check_balance(pair['fee_distributor_address'], token['address'])['diff']
        if missing_amount > 0:
            check = {
               'symbol': token['symbol'],
               'address': token['address'],
               'missing_amount': missing_amount / 10 ** token['decimals']
            }
            result.append(check)

    return jsonify({
        'fee_distributor_address': fee_distributor_address,
        'result': result
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0")
