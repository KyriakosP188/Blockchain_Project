from transaction import Transaction
from Crypto.PublicKey import RSA
from collections import deque

class Wallet:
	def __init__(self):
        # wallet initialization
		key = RSA.generate(1024)
		self.private_key = key.exportKey().decode('ISO-8859-1')
		self.public_key = key.publickey().exportKey().decode('ISO-8859-1')
		self.UTXOs = deque()

	def wallet_balance(self):
		# computes wallet balance
		balance = 0
		for utxo in self.UTXOs:
			balance += utxo['value']
		return balance