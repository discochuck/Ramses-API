import os

from web3 import Web3
import redis

w3 = Web3(Web3.HTTPProvider('https://endpoints.omniatech.io/v1/arbitrum/one/public'))

RAM_ADDRESS = '0xAAA6C1E32C55A7Bfa8066A6FAE9b42650F262418'.lower()

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
