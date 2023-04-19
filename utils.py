import os

from web3 import Web3
import redis

w3 = Web3(Web3.HTTPProvider('https://arbitrum.blockpi.network/v1/rpc/public'))

database_url = os.environ.get('DATABASE_URL')
if database_url:
    db = redis.Redis().from_url(database_url)

    cache_config = {
        'CACHE_TYPE': 'RedisCache',
        'CACHE_REDIS_URL': database_url
    }
else:
    db = redis.Redis()

    cache_config = {
        'CACHE_TYPE': 'RedisCache'
    }


def log(msg):
    print(msg)
