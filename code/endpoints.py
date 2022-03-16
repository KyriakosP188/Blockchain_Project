from flask import Blueprint, jsonify, request
from threading import Thread
from copy import deepcopy
from time import sleep
from node import Node
import requests
import pickle
import config

NODES = config.NUMBER_OF_NODES

node = Node()
rest_api = Blueprint('rest_api', __name__)

# ------------------------------------------
# ------------- Node endpoints -------------
# ------------------------------------------

@rest_api.route('/register_node', methods=['POST'])
def register_node():
    # registers node to the ring (only called by bootstrap node)
    node_public_key = request.form.get('public_key')
    node_ip = request.form.get('ip')
    node_port = request.form.get('port')
    node_id = len(node.ring)

    node.register_node_to_ring(node_id, node_ip, node_port, node_public_key, 0, [])

    if len(node.ring) == NODES:
        # bootstrap node sends the ring and chain to all other nodes
        def thread_function(n, responses):
            response = requests.post('http://' + n['ip'] + ':' + n['port'] + '/receive_ring_and_chain',
                                    data=pickle.dumps((node.ring, node.chain)))
            responses.append(pickle.loads(response.status_code))

        threads = []
        responses = []
        for n in node.ring:
            if n['id'] != 0:
                thread = Thread(target=thread_function, args=(n, responses))
                threads.append(thread)
                thread.start()

        for t in threads:
            t.join()

        # then creates a transaction, giving 100 NBC to each node
        for n in node.ring:
            if n['id'] != 0:
                node.create_transaction(n['public_key'], 100)

    return jsonify({'id': node_id})

@rest_api.route('/receive_ring_and_chain', methods=['POST'])
def share_ring_and_chain():
    # receive bootstrap's node ring and chain, only called by bootstrap node on startup
    (ring, chain) = pickle.loads(request.get_data())
    node.ring = deepcopy(ring)
    node.chain = deepcopy(chain)
    return jsonify({'message': "OK"}), 200

@rest_api.route('/register_transaction', methods=['POST'])
def register_transaction():
    # adds incoming transaction to block if valid
    transaction = pickle.loads(request.get_data())
    if node.validate_transaction(transaction):
        # update wallet UTXOs
        if node.wallet.public_key == transaction.sender_address:
            node.wallet.UTXOs.append(transaction.transaction_outputs[0])
        elif node.wallet.public_key == transaction.receiver_address:
            node.wallet.UTXOs.append(transaction.transaction_outputs[1])
        # update ring balance and utxos
        for n in node.ring:
            if n['public_key'] == transaction.sender_address:
                n['balance'] -= transaction.amount
                n['utxos'] = n.wallet.UTXOs
            elif n['public_key'] == transaction.receiver_address:
                n['balance'] += transaction.amount
                n['utxos'] = n.wallet.UTXOs
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
                # update wallet UTXOs
                if node.wallet.public_key == t.sender_address:
                    node.wallet.UTXOs.append(t.transaction_outputs[0])
                elif node.wallet.public_key == t.receiver_address:
                    node.wallet.UTXOs.append(t.transaction_outputs[1])
                # update ring balance and utxos
                for n in node.ring:
                    if n['public_key'] == t.sender_address:
                        n['balance'] -= t.amount
                        n['utxos'] = n.wallet.UTXOs
                    elif n['public_key'] == t.receiver_address:
                        n['balance'] += t.amount
                        n['utxos'] = n.wallet.UTXOs
    else:
        node.resolve_conflicts()
    node.mine = True
    return jsonify({'message': "OK"}), 200

@rest_api.route('/send_chain_and_id', methods=['GET'])
def send_chain_and_id():
    # sends chain and id of this node
    return pickle.dumps((node.chain, node.id))

@rest_api.route('/send_ring_and_pending_transactions', methods=['GET'])
def send_ring_and_pending_transactions():
    # sends ring and pending transactions list of this node
    return pickle.dumps((node.ring, node.pending_transactions))

# ------------------------------------------
# -------------- CLI endpoints -------------
# ------------------------------------------

@rest_api.route('/create_new_transaction', methods=['POST'])
def create_new_transaction():
    # creates new transaction
    (receiver_address, amount) = pickle.loads(request.get_data())
    node.create_new_transaction(receiver_address, amount)
    if amount > node.wallet.wallet_balance():
        return jsonify({'message': "Transaction failed. Not enough coins."}), 402
    return jsonify({'message': "OK"}), 200

@rest_api.route('/view_last_transactions', methods=['GET'])
def view_last_transactions():
    # returns the transactions that are in the last validated block of the chain
    return pickle.dumps(node.chain.blocks[-1].transactions)

@rest_api.route('/get_balance', methods=['GET'])
def get_balance():
    # returns the balance of this node's wallet
    return pickle.dumps(node.wallet.wallet_balance())