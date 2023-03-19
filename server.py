from flask import Flask, jsonify
from flask_caching import Cache
from flask_cors import CORS

from get_apr import get_apr

app = Flask(__name__)

CORS(app)
cache = Cache(app)


@app.route("/")
@cache.cached(60 * 60)
def test():
    return jsonify(get_apr())
