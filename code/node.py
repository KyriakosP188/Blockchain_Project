from more_itertools import first
from transaction import Transaction
from blockchain import Blockchain
from collections import deque
from threading import Thread
from wallet import Wallet
from block import Block
import requests
import config
import pickle

DIFFICULTY = config.MINING_DIFFICULTY
CAPACITY = config.BLOCK_CAPACITY
NODES = config.NUMBER_OF_NODES

class Node:
	def __init__(self, id=None):
		self.id = id
		self.chain = Blockchain()
		self.wallet = Wallet()
		self.ring = [] # here we store id, address(ip:port), public key, and balance for every node
		self.pending_transactions = deque()
		Thread(target=self.mining_handler).start()
		self.mine = True

	def create_genesis_block(self):
		# creates the genesis block (only called by bootstrap node on start-up)
		first_transaction = Transaction('0', self.wallet.public_key, 100 * NODES, [], self.wallet.private_key)
		self.wallet.UTXOs.append(first_transaction.transaction_outputs[1])
		genesis_block = Block(0, [first_transaction], 1)
		self.chain.blocks.append(genesis_block)

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
		if self.wallet.wallet_balance() >= amount:
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

		self.broadcast_transaction(new_transaction)

		if self.validate_transaction(new_transaction):
			# update ring balance
			for node in self.ring:
				if node['public_key'] == new_transaction.sender_address:
					node['balance'] -= new_transaction.amount
				elif node['public_key'] == new_transaction.receiver_address:
					node['balance'] += new_transaction.amount
			# update wallet UTXOs
			if self.wallet.public_key == new_transaction.sender_address:
				self.wallet.UTXOs.append(new_transaction.transaction_outputs[0])
			elif self.wallet.public_key == new_transaction.receiver_address:
				self.wallet.UTXOs.append(new_transaction.transaction_outputs[1])
			# add transaction to block
			self.pending_transactions.append(new_transaction)
			return True
		else:
			# if transaction is invalid revert UTXOs
			self.wallet.UTXOs.extend(backup)
			return False

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
		def thread_function(node, responses):
			response = requests.post('http://' + node['ip'] + ':' + node['port'] + '/register_transaction',
									data=pickle.dumps(transaction))
			responses.append(response.status_code)

		threads = []
		responses = []
		for node in self.ring:
			if node['id'] != self.id:
				thread = Thread(target=thread_function, args=(node, responses))
				threads.append(thread)
				thread.start()

	def mining_handler(self):
		# mines block, broadcasts it if node wins the competition and adds it to the chain if it's valid
		while True:
			if len(self.pending_transactions) >= CAPACITY and self.mine:
				transactions = [self.pending_transactions.popleft() for _ in range(CAPACITY)]
				block_to_mine = Block(len(self.chain.blocks), transactions, self.chain.blocks[-1].current_hash)
				self.mine_block(block_to_mine)
				if self.mine:
					# broadcast block
					self.broadcast_block(block_to_mine)
					# add block to chain if valid
					if not self.chain.add_block(block_to_mine):
						self.pending_transactions.extendleft(transactions)
				else:
					self.pending_transactions.extendleft(transactions)

	def mine_block(self, block):
		# mines the given block
		while not block.current_hash.startswith('0' * DIFFICULTY) and self.mine:
			block.nonce += 1
			block.current_hash = block.calc_hash()

	def broadcast_block(self, block):
		# broadcasts mined block
		def thread_function(node, responses):
			response = requests.post('http://' + node['ip'] + ':' + node['port'] + '/register_block',
									data=pickle.dumps(block))
			responses.append(response.status_code)

		threads = []
		responses = []
		for node in self.ring:
			if node['id'] != self.id:
				thread = Thread(target=thread_function, args=(node, responses))
				threads.append(thread)
				thread.start()

	def resolve_conflicts(self):
		# resolves conflict by selecting the longest valid chain
		return