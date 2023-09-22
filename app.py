import json

import os
import requests
from flask import Flask, jsonify, request
from flask_caching import Cache
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


from claimable_rewards import get_voter_claimable_rewards
from get_apr import get_apr, get_pairs, _fetch_pairs
from utils import db, cache_config
from v2.pairs import get_pairs_v2
from v2.tokenlist import get_tokenlist
from cl.pools import get_cl_pools, get_mixed_pairs

app = Flask(__name__)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20 per second"],
    storage_uri=os.environ.get('DATABASE_URL'),
)

CORS(app)
cache = Cache(app, config=cache_config)


# Deprecated
@app.route("/")
@cache.cached(60 * 60)
def apr():
    try:
        apr = get_apr()
        # todo notify admin
    except:
        apr = json.loads(db.get("apr"))

    return jsonify(apr)


# Deprecated
@app.route("/pairs")
@cache.cached(60 * 5)
def pairs():
    print("function call")
    from get_apr import get_pairs

    return jsonify(get_pairs())


@app.route("/v2/pairs")
@cache.cached(60 * 5)
def v2_pairs():
    return jsonify(get_pairs_v2())


@app.route("/v2/tokenlist")
@cache.cached(60 * 5)
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
@cache.cached(60 * 5)
def cl_pools():
    return jsonify(get_cl_pools())


@app.route("/mixed-pairs")
@cache.cached(60 * 5)
def mixed_pairs():
    return jsonify(get_mixed_pairs())


if __name__ == "__main__":
    app.run(host="0.0.0.0")
