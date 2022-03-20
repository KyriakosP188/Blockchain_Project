from flask import Blueprint, jsonify, request
from threading import Thread, Lock, Event
from time import sleep
from node import Node
import requests
import pickle
import config
import random

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

    if len(node.ring) == config.NUMBER_OF_NODES:
        # bootstrap node sends the ring and chain to all other nodes
        def bootstrap_thread():
            def thread_function(n, responses):
                response = requests.post('http://' + n['ip'] + ':' + n['port'] + '/receive_ring_and_chain',
                                        data=pickle.dumps((node.ring, node.chain)))
                responses.append(response.status_code)

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
                    sleep(random.random() * 5)

        Thread(target=bootstrap_thread).start()

    return jsonify({'id': node_id}), 200

@rest_api.route('/receive_ring_and_chain', methods=['POST'])
def share_ring_and_chain():
    # receive bootstrap's node ring and chain, only called by bootstrap node on startup
    (ring, chain) = pickle.loads(request.get_data())
    node.ring = ring
    node.chain = chain
    return jsonify({'message': "OK"}), 200

@rest_api.route('/register_transaction', methods=['POST'])
def register_transaction():
    # adds incoming transaction to block if valid
    transaction = pickle.loads(request.get_data())
    if node.validate_transaction(transaction):
        # update wallet UTXOs
        node.update_wallet(transaction)
        # update ring balance and utxos
        node.update_ring(transaction)
        # add transaction to block
        node.pending_transactions.append(transaction)
        return jsonify({'message': "OK"}), 200
    else:
        return jsonify({'message': "The transaction is invalid"}), 401

@rest_api.route('/register_block', methods=['POST'])
def register_block():
    # adds incoming block to the chain if valid
    node.pause_thread.set()
    node.block_lock.acquire()
    block = pickle.loads(request.get_data())
    if block.index == node.chain.blocks[-1].index + 1 and node.chain.add_block(block):
        # remove mutual transactions between pending and block
        pending = set([t.transaction_id for t in node.pending_transactions])
        block_transactions = set([t.transaction_id for t in block.transactions])
        node.pending_transactions = [t for t in node.pending_transactions if t.transaction_id in (pending - block_transactions)]
        transactions_to_register = [t for t in block.transactions if t.transaction_id in (block_transactions - pending)]
        # for transactions that are not in pending list, register
        for transaction in transactions_to_register:
            # update wallet UTXOs
            node.update_wallet(transaction)
            # update ring balance and utxos
            node.update_ring(transaction)
    else:
        node.resolve_conflicts()
    node.block_lock.release()
    node.pause_thread.clear()
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
    (receiver_id, amount) = pickle.loads(request.get_data())
    receiver_address = None
    for n in node.ring:
        if receiver_id == n['id']:
            receiver_address = n['public_key']
    if receiver_address != None and receiver_address != node.wallet.public_key:
        if node.create_transaction(receiver_address, amount):
            return jsonify({'message': "OK"}), 200
        else:
            return jsonify({'message': "Transaction failed. Not enough coins or signature is invalid."}), 402
    elif receiver_address == None:
        return jsonify({'message': "Transaction failed. There is no node with the given ID."}), 403
    else:
        return jsonify({'message': "Transaction failed. You cannot send coins to yourself."}), 404

@rest_api.route('/view_last_transactions', methods=['GET'])
def view_last_transactions():
    # returns the transactions that are in the last validated block of the chain
    return pickle.dumps(node.chain.blocks[-1].transactions)

@rest_api.route('/get_balance', methods=['GET'])
def get_balance():
    # returns the balance of this node's wallet
    return pickle.dumps((node.wallet.wallet_balance(), node.ring))