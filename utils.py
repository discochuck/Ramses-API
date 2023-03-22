from web3 import Web3
import redis

w3 = Web3(Web3.HTTPProvider('https://arbitrum.blockpi.network/v1/rpc/public'))

# db = redis.Redis(host='localhost', port=6379, db=0)

db = redis.Redis(
    host='db-redis-lon1-64155-do-user-13783795-0.b.db.ondigitalocean.com',
    port=25061,
    username="default",
    password="l9IiehUd4w6QpsSSH3F",
    db=0
)
