from transaction import Transaction
from blockchain import Blockchain
from collections import deque
from wallet import Wallet
from block import Block
import requests
import config

DIFFICULTY = config.MINING_DIFFICULTY

class Node:
	def __init__(self, id):
		self.id = id
		if id == 0:
			self.create_genesis_block()
		self.chain = Blockchain()
		self.current_block = None
		self.wallet = Wallet()
		self.ring = [] # here we store id, address(ip:port), public key, and balance for every node

	def create_genesis_block(self):
		genesis = Block(0, 1)

	def create_new_block(self):
		# index and previous_hash will be updated during mining
		self.current_block = Block(None, None)

	def register_node_to_ring(self, id, ip, port, public_key, balance):
		# adds this node to the ring (called only by bootstrap node)
		self.ring.append({
			'id': id,
            'ip': ip,
            'port': port,
            'public_key': public_key,
            'balance': balance
        })

	def create_transaction(self, receiver_address, amount):
		# creates a new transaction
		backup = deque()
		transaction_inputs = []
		balance = 0
		if self.wallet.wallet_balance() > amount:
			while balance < amount:
				utxo = self.wallet.UTXOs.pop()
				balance += utxo['value']
				input = {
					'id': utxo['transaction_id'],
					'value': utxo['value']
				}
				transaction_inputs.append(input)
				backup.append(utxo)
		else:
			return False
		new_transaction = Transaction(self.wallet.public_key, receiver_address, amount, transaction_inputs, self.wallet.private_key)

		if not self.broadcast_transaction(new_transaction):
			# if transaction is invalid revert UTXOs
			self.wallet.UTXOs.extend(backup)
			return False

		return True

	def validate_transaction(self, transaction):
		# validates incoming transaction
		if not transaction.verify_signature():
			return False

		for node in self.ring:
			if node['public_key'] == transaction.sender_address:
				if node['balance'] >= transaction.amount:
					return True

		return False

	def broadcast_transaction(self, transaction):
		# broadcasts transaction to the ring
		# add_transaction_to_block(self):
		

	def add_transaction_to_block(self):
		# if enough transactions  mine
		# def mine_block(self, block):
		# def broadcast_block(self):


	def mine_block(self, block):
		# mines the given block
		block.index = self.chain.blocks[-1].index + 1
		block.previous_hash = self.chain.blocks[-1].current_hash

		while not block.current_hash.startswith('0' * DIFFICULTY):
			block.nonce += 1
			block.current_hash = block.calc_hash()

	def broadcast_block(self):
		# 
		

	def resolve_conflicts(self):
		# resolve correct chain
		new_chain = None
		max_length = len(self.chain)

		for node in self.ring:
			if node['node_id'] != self.current_id:
				response = requests.get(node['ip_address'] + '/chain')

				if response.status_code == 200:
					length = response.json()['length']
					chain = response.json()['chain']

					if length > max_length:
						max_length = length
						new_chain = chain

		if new_chain:
			self.chain = new_chain
			return True

		return False