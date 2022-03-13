from transaction import Transaction
from threading import Thread, Lock
from blockchain import Blockchain
from collections import deque
from copy import deepcopy
from wallet import Wallet
from block import Block
import requests
import config
import pickle

DIFFICULTY = config.MINING_DIFFICULTY

class Node:
	def __init__(self, id=None):
		self.id = id
		if id == 0:
			self.create_genesis_block()
		self.chain = Blockchain()
		self.current_block = None
		self.wallet = Wallet()
		self.ring = [] # here we store id, address(ip:port), public key, and balance for every node
		self.block_pool = deque()
		self.mine = True
		self.mine_lock = Lock()
		self.loop = True

	def create_genesis_block(self):
		# creates the genesis block (only called by bootrstrap node on start-up)
		self.current_block = Block(0, 1)

	def create_new_block(self):
		# creates a new block, index and previous_hash will be updated during mining
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
		# broadcasts transaction to the ring and calls add_transaction_to_block if everyone agrees it's valid
		def thread_function(node, responses, endpoint):
			# calls the given endpoint for each other node and appends response to list
			if node['id'] != self.id:
				response = requests.post('http://' + node['ip'] + ':' + node['port'] + endpoint,
										data=pickle.dumps(transaction))
				responses.append(response.status_code)

		# broadcast transaction to all nodes
		threads = []
		responses = []
		for node in self.ring:
			thread = Thread(target=thread_function, args=(node, responses, '/validate_transaction'))
			threads.append(thread)
			thread.start()

		for t in threads:
			# wait for all the threads to finish
			t.join()

		for response in responses:
			if response != 200:
				return False

		# add transaction to the current block of all nodes
		threads = []
		responses = []
		for node in self.ring:
			thread = Thread(target=thread_function, args=(node, responses, '/add_transaction_to_block'))
			threads.append(thread)
			thread.start()

		self.add_transaction_to_block(transaction)
		return True

	def add_transaction_to_block(self, transaction):
		# adds transaction to the current block, if block is full mine it
		# transaction is valid, so we update wallets and lists involved
		

		if not self.current_block.add_transaction(transaction):
			# block is full
			self.block_pool.append(deepcopy(self.current_block))
			self.create_new_block()
			if self.loop:
				# mine loop
				while True:
					self.loop = False
					if self.block_pool:
						self.mine_lock.acquire()
						block_to_mine = self.block_pool.popleft()
						self.mine_block(block_to_mine)
						self.mine_lock.release()
						if self.mine:
							# winner broadcasts block
							self.broadcast_block(block_to_mine)

	def mine_block(self, block):
		# mines the given block
		block.index = self.chain.blocks[-1].index + 1
		block.previous_hash = self.chain.blocks[-1].current_hash
		while not block.current_hash.startswith('0' * DIFFICULTY) and self.mine:
			block.nonce += 1
			block.current_hash = block.calc_hash()

	def broadcast_block(self, block):
		# broadcasts mined block
		def thread_function(node, responses):
			if node['id'] != self.id:
				response = requests.post('http://' + node['ip'] + ':' + node['port'] + '/add_block_to_chain',
										data=pickle.dumps(block))
				responses.append(response.status_code)

		threads = []
		responses = []
		for node in self.ring:
			thread = Thread(target=thread_function, args=(node, responses))
			threads.append(thread)
			thread.start()

		self.chain.add_block(block)

	def resolve_conflicts(self):
		# resolves conflict by selecting the longest valid chain
		new_chain = None
		max_length = len(self.chain)

		for node in self.ring:
			if node['node_id'] != self.current_id:
				response = requests.get(node['ip_address'] + '/get_chain')

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