from argparse import ArgumentParser
from transaction import Transaction
from copy import deepcopy
from flask import Flask
from block import Block
from node import Node
import requests
import config
import socket

BOOTSTRAP_IP = config.BOOTSTRAP_IP
BOOTSTRAP_PORT = config.BOOTSTRAP_PORT

# Get the IP address of the device.
if config.LOCAL:
    IP_address = BOOTSTRAP_IP
else:
    hostname = socket.gethostname()
    IP_address = socket.gethostbyname(hostname)

if __name__ == "__main__":
    # define the argument parser
    parser = ArgumentParser(description='REST API of noobcash.')
    parser.add_argument('-p',
                        '--port',
                        type=int,
                        help='The port to listen on.',
                        required=True)
    parser.add_argument('-d',
                        '--difficulty',
                        type=int,
                        help='The mining difficulty of a new block.',
                        required=True)
    parser.add_argument('-n',
                        '--nodes',
                        type=int,
                        help='The number of nodes in the blockchain.',
                        required=True)
    parser.add_argument('-c',
                        '--capacity',
                        type=int,
                        help='The transaction capacity of a block.',
                        required=True)
    parser.add_argument('-b',
                        '--bootstrap',
                        action='store_true',
                        help='Start noobcash as the bootstrap node.')

    # parse the arguments
    args = parser.parse_args()
    port = args.port
    config.MINING_DIFFICULTY = args.difficulty
    config.NUMBER_OF_NODES = args.nodes
    config.BLOCK_CAPACITY = args.capacity
    is_bootstrap = args.bootstrap

    from endpoints import node, rest_api

    # Define the flask environment and register the blueprint with the endpoints.
    app = Flask(__name__)
    app.register_blueprint(rest_api)

    if is_bootstrap:
        node.id = 0
        # create the genesis block
        # add the first transaction to it
        # add it to the chain
        node.create_genesis_block()
        # register bootstrap node in the ring
        node.register_node_to_ring(0, BOOTSTRAP_IP, BOOTSTRAP_PORT, node.wallet.public_key, node.wallet.wallet_balance(), deepcopy(node.wallet.UTXOs))
        # listen in the specified address (ip:port)
        app.run(host=BOOTSTRAP_IP, port=BOOTSTRAP_PORT)
    else:
        # call bootstrap to register node in the ring
        response = requests.post('http://' + BOOTSTRAP_IP + ':' + BOOTSTRAP_PORT + '/register_node',
                                data={'public_key': node.wallet.public_key, 'ip': IP_address, 'port': port})

        if response.status_code != 200:
            print('Error initializing node.')
        else:
            print('Node initialized.')

        node.id = response.json()['id']

        # Listen in the specified address (ip:port)
        app.run(host=IP_address, port=port)