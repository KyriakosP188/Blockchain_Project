from hashlib import sha256
import config
import time
import json

CAPACITY = config.BLOCK_CAPACITY
DIFFICULTY = config.MINING_DIFFICULTY

class Block:
	def __init__(self, index, previous_hash):
		# block initialization
		self.index = index
		self.timestamp = time.time()
		self.transactions = []
		self.nonce = 0
		self.current_hash = self.calc_hash()
		self.previous_hash = previous_hash

	def calc_hash(self):
		# calculates current hash of block
		block_string = json.dumps({
            "timestamp": self.timestamp,
            "transactions": self.transactions,
			"nonce": self.nonce,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
		return sha256(block_string).hexdigest()

	def add_transaction(self, transaction):
		# adds new block transaction
		if len(self.transactions) < CAPACITY:
			self.transactions.append(transaction)
			return True
		return False

	def mine_block(self):
		# mines this block
		while not self.current_hash.startswith('0' * DIFFICULTY):
			self.nonce += 1
			self.current_hash = self.calc_hash()