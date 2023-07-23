from requests.adapters import HTTPAdapter, Retry
from threading import Thread, Lock, Event
from transaction import Transaction
from blockchain import Blockchain
from copy import deepcopy
import concurrent.futures
from wallet import Wallet
from block import Block
import requests
import config
import pickle
import time

def poll_endpoint(url, request_type='post', data=None):
	s = requests.Session()
	r = None
	retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
	s.mount('http://', HTTPAdapter(max_retries=retries))
	if request_type == 'post':
		r = s.post(url, data=data)
	else:
		r = s.get(url, data=data)
	return r

class Node:
	def __init__(self, id=None):
		self.id = id
		self.chain = Blockchain()
		self.wallet = Wallet()
		self.pending_transactions = []
		self.ring = [] # here we store id, address(ip:port), public key, and balance for every node
		self.node_lock = Lock()
		self.block_lock = Lock()
		self.block_time_lock = Lock()
		self.validated_transactions_lock = Lock()
		self.mine_thread = Thread(target=self.mining_handler)
		self.pause_thread = Event()
		self.mine_thread.start()

	def create_genesis_block(self):
		# creates the genesis block (only called by bootstrap node on start-up)
		first_transaction = Transaction('0', self.wallet.public_key, 100 * config.NUMBER_OF_NODES, [], self.wallet.private_key)
		self.wallet.UTXOs.append(first_transaction.transaction_outputs[1])
		genesis_block = Block(0, [first_transaction], 1)
		self.chain.blocks.append(genesis_block)

	def register_node_to_ring(self, id, ip, port, public_key, balance, utxos):
		# adds this node to the ring (called only by bootstrap node)
		self.ring.append({
			'id': id,
            'ip': ip,
            'port': port,
            'public_key': public_key,
            'balance': balance,
			'utxos': utxos
        })

	def create_transaction(self, receiver_address, amount):
		# creates a new transaction
		self.node_lock.acquire()
		transaction_inputs = []
		backup = []
		balance = 0
		if self.wallet.wallet_balance() >= amount:
			while balance < amount:
				utxo = self.wallet.UTXOs.pop()
				balance += utxo['value']
				input = {
					'id': utxo['id'],
					'value': utxo['value']
				}
				transaction_inputs.append(input)
				backup.append(utxo)
		else:
			self.node_lock.release()
			return False
		new_transaction = Transaction(self.wallet.public_key, receiver_address, amount, transaction_inputs, self.wallet.private_key)

		if self.validate_transaction(new_transaction):
			self.write_validated_transactions()
			# update wallet UTXOs
			self.update_wallet(new_transaction)
			# update ring balance and utxos
			self.update_ring(new_transaction)
			# add transaction to block
			self.pending_transactions.append(new_transaction)
			transaction_pickled = pickle.dumps(new_transaction)
			Thread(target=self.broadcast, args=('/register_transaction', deepcopy(transaction_pickled))).start()
			self.node_lock.release()
			return True
		else:
			# if transaction is invalid revert UTXOs
			self.wallet.UTXOs.extend(backup)
			self.node_lock.release()
			return False

	def update_wallet(self, transaction):
		# update wallet UTXOs
		if self.wallet.public_key == transaction.sender_address:
			self.wallet.UTXOs.append(transaction.transaction_outputs[0])
		elif self.wallet.public_key == transaction.receiver_address:
			self.wallet.UTXOs.append(transaction.transaction_outputs[1])

	def update_ring(self, transaction):
		# update ring balance and utxos
		for node in self.ring:
			if node['public_key'] == transaction.sender_address:
				node['balance'] -= transaction.amount

				spent_utxos = set([t['id'] for t in transaction.transaction_inputs])
				current_utxos = set([t['id'] for t in node['utxos']])
				node['utxos'] = [t for t in node['utxos'] if t['id'] in (current_utxos - spent_utxos)]

				node['utxos'].append(transaction.transaction_outputs[0])
			elif node['public_key'] == transaction.receiver_address:
				node['balance'] += transaction.amount
				node['utxos'].append(transaction.transaction_outputs[1])

	def validate_transaction(self, transaction):
		# validates incoming transaction
		if not transaction.verify_signature():
			return False

		for node in self.ring:
			if node['public_key'] == transaction.sender_address:
				if node['balance'] >= transaction.amount:
					return True

		return False

	def broadcast(self, url, obj, requests_function=requests.post):
		def make_request(url):
			if requests_function == requests.post:
				return poll_endpoint(url, request_type='post', data=obj)
			else:
				return poll_endpoint(url, request_type='get', data=obj)

		url_list = [
            f"http://{node['ip']}:{node['port']}{url}" for node in self.ring
            if node['public_key'] != self.wallet.public_key
        ]

		with concurrent.futures.ThreadPoolExecutor() as executor:
			responses = [executor.submit(make_request, url) for url in url_list]
			concurrent.futures.wait(responses)

		return [r.result() for r in responses]

	def mining_handler(self):
		# mines block, broadcasts it if node wins the competition and adds it to the chain if it's valid
		while True:
			if self.pause_thread.is_set():
				continue
			self.block_lock.acquire()
			if len(self.pending_transactions) >= config.BLOCK_CAPACITY:
				transactions = [self.pending_transactions.pop() for _ in range(config.BLOCK_CAPACITY)]
				block_to_mine = Block(len(self.chain.blocks), transactions, self.chain.blocks[-1].current_hash)
				if self.mine_block(block_to_mine):
					self.write_mine_time()
					print('+--------------+')
					print('| Block mined! |')
					print('+--------------+')
					# add block to chain if valid
					if self.chain.add_block(block_to_mine):
						self.write_block_time()
						# broadcast block
						block_pickled = pickle.dumps(block_to_mine)
						Thread(target=self.broadcast, args=('/register_block', deepcopy(block_pickled))).start()
					else:
						self.pending_transactions.extend(transactions)
				else:
					self.pending_transactions.extend(transactions)
			self.block_lock.release()

	def mine_block(self, block):
		# mines the given block
		while not block.current_hash.startswith('0' * config.MINING_DIFFICULTY):
			if self.pause_thread.is_set():
				print('+-----------------+')
				print('| Stopped mining! |')
				print('+-----------------+')
				return False
			block.nonce += 1
			block.current_hash = block.calc_hash()
		return True

	def resolve_conflicts(self):
		# resolves conflict by selecting the longest valid chain
		responses = self.broadcast('/send_chain_and_id', None, requests_function=requests.get)
		responses = [pickle.loads(r._content) for r in responses]

		max_chain_length = len(self.chain.blocks)
		max_chain = self.chain
		max_node_id = self.id
		for response in responses:
			if response[0].validate_chain():
				if len(response[0].blocks) > max_chain_length:
					max_chain_length = len(response[0].blocks)
					max_chain = response[0]
					max_node_id = response[1]

		if max_node_id != self.id:
			self.write_block_time()
			# get ring from node with the longest valid chain
			for node in self.ring:
				if node['id'] == max_node_id:
					ip = node['ip']
					port = node['port']

			response = poll_endpoint('http://' + ip + ':' + port + '/send_ring_and_pending_transactions', request_type='get')
			(ring, pending_transactons) = pickle.loads(response._content)

			self.pending_transactions = pending_transactons
			self.chain = max_chain
			self.ring = ring
			for node in self.ring:
				if node['id'] == self.id:
					self.wallet.UTXOs = deepcopy(node['utxos'])

	def write_block_time(self):
		self.block_time_lock.acquire()
		folder = f'{config.NUMBER_OF_NODES}-{config.MINING_DIFFICULTY}-{config.BLOCK_CAPACITY}'
		target = f'block_time-{config.PORT}-{config.NUMBER_OF_NODES}-{config.MINING_DIFFICULTY}-{config.BLOCK_CAPACITY}.txt'
		# with open('../../logs/' + folder + '/' + target, 'a') as file:
		# 	file.write(str(time.time()) + '\n')
		self.block_time_lock.release()

	def write_mine_time(self):
		folder = f'{config.NUMBER_OF_NODES}-{config.MINING_DIFFICULTY}-{config.BLOCK_CAPACITY}'
		target = f'mine-{config.PORT}-{config.NUMBER_OF_NODES}-{config.MINING_DIFFICULTY}-{config.BLOCK_CAPACITY}.txt'
		# with open('../../logs/' + folder + '/' + target, 'a') as file:
		# 	file.write(str(time.time()) + '\n')

	def write_validated_transactions(self):
		self.validated_transactions_lock.acquire()
		folder = f'{config.NUMBER_OF_NODES}-{config.MINING_DIFFICULTY}-{config.BLOCK_CAPACITY}'
		target = f'validated_transactions-{config.PORT}-{config.NUMBER_OF_NODES}-{config.MINING_DIFFICULTY}-{config.BLOCK_CAPACITY}.txt'
		# with open('../../logs/' + folder + '/' + target, 'a') as file:
		# 	file.write(str(1) + '\n')
		self.validated_transactions_lock.release()