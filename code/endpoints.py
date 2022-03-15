from flask import Blueprint, jsonify, request
from time import sleep
from node import Node
import pickle

node = Node()
rest_api = Blueprint('rest_api', __name__)

# ------------------------------------------
# ------------- Node endpoints -------------
# ------------------------------------------

@rest_api.route('/register_node', methods=['POST'])
def register_node():
    # registers node to the ring (only called by bootstrap node)
    return

@rest_api.route('/register_transaction', methods=['POST'])
def register_transaction():
    # adds incoming transaction to block if valid
    transaction = pickle.loads(request.get_data())
    if node.validate_transaction(transaction):
        # update ring balance
        for node in node.ring:
            if node['public_key'] == transaction.sender_address:
                node['balance'] -= transaction.amount
            elif node['public_key'] == transaction.receiver_address:
                node['balance'] += transaction.amount
        # update wallet UTXOs
        if node.wallet.public_key == transaction.sender_address:
            node.wallet.UTXOs.append(transaction.transaction_outputs[0])
        elif node.wallet.public_key == transaction.receiver_address:
            node.wallet.UTXOs.append(transaction.transaction_outputs[1])
        # add transaction to block
        node.pending_transactions.append(transaction)
        return jsonify({'message': "OK"}), 200
    else:
        return jsonify({'message': "The transaction is invalid"}), 401

@rest_api.route('/register_block', methods=['POST'])
def register_block():
    # adds incoming block to the chain if valid
    node.mine = False
    sleep(3) # wait for mine loop to break
    block = pickle.loads(request.get_data())
    if node.chain.add_block(block):
        for t in block.transactions:
            if t in node.pending_transactions:
                # remove completed transactions from node's pending transactions
                node.pending_transactions.remove(t)
            else:
                # update ring balance
                for node in node.ring:
                    if node['public_key'] == t.sender_address:
                        node['balance'] -= t.amount
                    elif node['public_key'] == t.receiver_address:
                        node['balance'] += t.amount
                # update wallet UTXOs
                if node.wallet.public_key == t.sender_address:
                    node.wallet.UTXOs.append(t.transaction_outputs[0])
                elif node.wallet.public_key == t.receiver_address:
                    node.wallet.UTXOs.append(t.transaction_outputs[1])
    else:
        node.resolve_conflicts()
    node.mine = True
    return jsonify({'message': "OK"}), 200

@rest_api.route('/get_chain', methods=['GET'])
def get_chain():
    # sends chain of this node
    return

# ------------------------------------------
# -------------- CLI endpoints -------------
# ------------------------------------------

@rest_api.route('/create_new_transaction', methods=['POST'])
def create_new_transaction():
    # creates new transaction
    return

@rest_api.route('/view_last_transactions', methods=['GET'])
def view_last_transactions():
    # returns the transactions that are in the last validated block of the chain
    return

@rest_api.route('/get_balance', methods=['GET'])
def get_balance():
    # returns the balance of this node's wallet
    return