import json

import requests
from flask import Flask, jsonify, request
from flask_caching import Cache
from flask_cors import CORS

from claimable_rewards import get_voter_claimable_rewards
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
# @cache.cached(60 * 60)
def pairs():
    print('function call')
    return jsonify(get_pairs())


@app.route("/firebird")
def firebird_proxy():
    url = f"https://router.firebird.finance/aggregator/v1/route?{request.query_string.decode()}"

    res = requests.get(
        url=url,
        headers={
            'API-KEY': 'firebird_ramses_prod_200323'
        }
    )

    print(res.status_code)
    if res.status_code == 200:
        return jsonify(res.json())
    else:
        return res.text


@app.route("/voterClaimableRewards")
def voter_claimable_rewards():
    token_id = request.args.get('token_id')
    return jsonify(
        get_voter_claimable_rewards(int(token_id))
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0")
