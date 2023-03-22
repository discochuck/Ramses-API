from web3 import Web3
import redis

w3 = Web3(Web3.HTTPProvider('https://arbitrum.blockpi.network/v1/rpc/public'))

db = redis.Redis(host='localhost', port=6379, db=0)
