from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from hashlib import sha256
import json
import uuid

class Transaction:
    def __init__(self, sender_address, receiver_address, amount, transaction_inputs, private_key):
        # transaction initialization
        self.sender_address = sender_address
        self.receiver_address = receiver_address
        self.amount = amount
        self.transaction_inputs = transaction_inputs
        self.transaction_id = self.calc_hash()
        self.transaction_outputs = self.compute_transaction_outputs()
        if private_key != None:
            self.signature = self.sign_transaction(private_key)

    def sign_transaction(self, private_key):
        # signs the transaction using the sender's private key
        message = self.transaction_id.encode("ISO-8859-1")
        key = RSA.importKey(private_key.encode("ISO-8859-1"))
        h = sha256.new(message)
        signer = pss.new(key)
        self.signature = signer.sign(h).decode('ISO-8859-1')

    def verify_signature(self):
        # verifies the signature of the transaction
        key = RSA.importKey(self.sender_address.encode('ISO-8859-1'))
        h = sha256.new(self.transaction_id.encode('ISO-8859-1'))
        verifier = pss.new(key)
        try:
            verifier.verify(h, self.signature.encode('ISO-8859-1'))
            return True
        except (ValueError, TypeError):
            return False

    def calc_hash(self):
        # calculates hash of the transaction
        transaction_string = json.dumps({
            "sender_address": self.sender_address,
            "receiver_address": self.receiver_address,
            "amount": self.amount,
            "transaction_inputs": self.transaction_inputs
        }, sort_keys=True).encode()
        return sha256(transaction_string).hexdigest()

    def compute_transaction_outputs(self):
        # computes the two outputs of the transaction
        balance = 0
        for input in self.transaction_inputs:
            balance += input['value']
        output1 = {
            'id': uuid.uuid4().int,
            'transaction_id': self.transaction_id,
            'recipient': self.sender_address,
            'value': balance - self.amount
        }
        output2 = {
            'id': uuid.uuid4().int,
            'transaction_id': self.transaction_id,
            'recipient': self.receiver_address,
            'value': self.amount
        }
        return [output1, output2]