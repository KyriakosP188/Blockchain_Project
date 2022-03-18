from flask import Blueprint, jsonify, request
from threading import Thread, Lock, Event
from copy import deepcopy
from node import Node
import requests
import pickle
import config

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
        
        Thread(target=bootstrap_thread).start()

    return jsonify({'id': node_id}), 200

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
        node.transaction_lock.acquire()
        # update wallet UTXOs
        if node.wallet.public_key == transaction.sender_address:
            node.wallet.UTXOs.append(transaction.transaction_outputs[0])
        elif node.wallet.public_key == transaction.receiver_address:
            node.wallet.UTXOs.append(transaction.transaction_outputs[1])
        # update ring balance and utxos
        for n in node.ring:
            if n['public_key'] == transaction.sender_address:
                n['balance'] -= transaction.amount
                spent_utxos = []
                for input in transaction.transaction_inputs:
                    for utxo in n['utxos']:
                        if input['id'] == utxo['id']:
                            spent_utxos.append(utxo)
                for s in spent_utxos:
                    n['utxos'].remove(s)
                n['utxos'].append(transaction.transaction_outputs[0])
            elif n['public_key'] == transaction.receiver_address:
                n['balance'] += transaction.amount
                n['utxos'].append(transaction.transaction_outputs[1])
        # add transaction to block
        node.pending_transactions.append(transaction)
        node.transaction_lock.release()
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
        node.transaction_lock.acquire()
        for t in block.transactions:
            remove_transcations = []
            t_bool = True
            for pt in node.pending_transactions:
                if t.transaction_id == pt.transaction_id:
                    # remove completed transactions from node's pending transactions
                    t_bool = False
                    remove_transcations.append(pt)
            if t_bool:
                # update wallet UTXOs
                if node.wallet.public_key == t.sender_address:
                    node.wallet.UTXOs.append(t.transaction_outputs[0])
                elif node.wallet.public_key == t.receiver_address:
                    node.wallet.UTXOs.append(t.transaction_outputs[1])
                # update ring balance and utxos
                for n in node.ring:
                    if n['public_key'] == t.sender_address:
                        n['balance'] -= t.amount
                        spent_utxos = []
                        for input in t.transaction_inputs:
                            for utxo in n['utxos']:
                                if input['id']== utxo['id']:
                                    spent_utxos.append(utxo)
                        for s in spent_utxos:
                            n['utxos'].remove(s)
                        n['utxos'].append(t.transaction_outputs[0])
                    elif n['public_key'] == t.receiver_address:
                        n['balance'] += t.amount
                        n['utxos'].append(t.transaction_outputs[1])
            for rt in remove_transcations:
                node.pending_transactions.remove(rt)
        node.transaction_lock.release()
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
    return pickle.dumps(node.wallet.wallet_balance())