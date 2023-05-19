import json

import requests
from flask import Flask, jsonify, request
from flask_caching import Cache
from flask_cors import CORS

from claimable_rewards import get_voter_claimable_rewards
from get_apr import get_apr, get_pairs, _fetch_pairs
from utils import db, cache_config
from v2.get_pairs import get_pairs_v2

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
@cache.cached(1 * 5)
def pairs():
    print('function call')
    from get_apr import get_pairs
    return jsonify(get_pairs())


@app.route("/dev/pairs")
def dev_pairs():
    return jsonify(_fetch_pairs(False))


@app.route("/voterClaimableRewards")
def voter_claimable_rewards():
    token_id = request.args.get('token_id')
    return jsonify(
        get_voter_claimable_rewards(int(token_id))
    )


@app.route("/v2/pairs")
@cache.cached(60 * 5)
def v2_pairs():
    return jsonify(get_pairs_v2())


if __name__ == "__main__":
    app.run(host="0.0.0.0")
