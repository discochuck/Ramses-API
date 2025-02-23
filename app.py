import json

import os
import requests
from flask import Flask, jsonify, request
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


from claimable_rewards import get_voter_claimable_rewards
from apr_backtest import get_backtested_cl_data
from get_apr import get_apr, get_pairs, _fetch_pairs
from utils import db, cache_config
from v2.pairs import get_pairs_v2
from v2.tokenlist import get_tokenlist
from cl.pools import get_cl_pools, get_mixed_pairs

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per second"],
    storage_uri=os.environ.get("DATABASE_URL"),
)

CORS(app)
cache = Cache(app, config=cache_config)
CACHE_DEFAULT_TIMEOUT = 60 * 2

# Deprecated
@app.route("/")
@cache.cached(CACHE_DEFAULT_TIMEOUT)
def apr():
    try:
        apr = get_apr()
        # todo notify admin
    except:
        apr = json.loads(db.get("apr"))

    return jsonify(apr)


# Deprecated
@app.route("/pairs")
@cache.cached(CACHE_DEFAULT_TIMEOUT)
def pairs():
    print("function call")
    from get_apr import get_pairs

    return jsonify(get_pairs())


# apr backtest
@app.route("/apr_backtest", methods=["GET"])
def get_apr_backtest():
    nft_ids = request.args.get("nft_ids")
    if not nft_ids:
        return jsonify({"error": "nft_ids not provided"}), 400

    nft_ids = [int(nft_id) for nft_id in nft_ids.split(",")]

    # Call get_cl_data with the nft_ids
    cl_data = get_backtested_cl_data(nft_ids)

    # Return the data as a JSON response
    return jsonify(cl_data)


@app.route("/v2/pairs")
@cache.cached(CACHE_DEFAULT_TIMEOUT)
def v2_pairs():
    return jsonify(get_pairs_v2())


@app.route("/v2/tokenlist")
@cache.cached(CACHE_DEFAULT_TIMEOUT)
def tokenlist():
    return jsonify(get_tokenlist())


@app.route("/dev/v2/pairs")
def dev_pairs():
    return jsonify(get_pairs_v2())


@app.route("/dev/cl-pools")
def dev_cl_pools():
    return jsonify(get_cl_pools(True))


@app.route("/voterClaimableRewards")
def voter_claimable_rewards():
    token_id = request.args.get("token_id")
    return jsonify(get_voter_claimable_rewards(int(token_id)))


@app.route("/unlimited-lge-chart")
def get_unlimited_lge_chart():
    limit = 100
    skip = 0
    data = []
    while True:
        query = f"{{ buys(skip: {skip}, limit: {limit}, orderBy: totalRaised) {{user timestamp amount totalRaised}} }}"
        response = requests.post(
            url="https://api.thegraph.com/subgraphs/name/sullivany/unlimited-lge", json={"query": query}
        )

        if response.status_code == 200:
            new_data = response.json()["data"]["buys"]
            data += new_data

            if len(new_data) < limit:
                break
            else:
                skip += limit
        else:
            return json.loads(db.get("unlimited-lge-chart"))

    db.set("unlimited-lge-chart", json.dumps(data))

    return data


@app.route("/cl-pools")
@cache.cached(CACHE_DEFAULT_TIMEOUT)
def cl_pools():
    return jsonify(get_cl_pools())


@app.route("/mixed-pairs")
@cache.cached(CACHE_DEFAULT_TIMEOUT)
def mixed_pairs():
    return jsonify(get_mixed_pairs())


if __name__ == "__main__":
    app.run(host="0.0.0.0")
