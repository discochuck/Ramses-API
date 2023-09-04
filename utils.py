import os

from web3 import Web3
import redis

w3 = Web3(Web3.HTTPProvider('https://arb1.arbitrum.io/rpc'))

RAM_ADDRESS = '0xAAA6C1E32C55A7Bfa8066A6FAE9b42650F262418'.lower()
VOTER_ADDRESS = '0xAAA2564DEb34763E3d05162ed3f5C2658691f499'.lower()
V1_FACTORY_ADDRESS = '0xAAA20D08e59F6561f242b08513D36266C5A29415'.lower()
fees = {
    'stable': 1,
    'variable': 20
}

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
