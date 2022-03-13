from endpoints import node, number_of_nodes, rest_api
from transaction import Transaction
from flask_cors import CORS
from flask import Flask
from block import Block
from node import Node
import threading
import requests
import time

app = Flask(__name__)
app.register_blueprint(rest_api)
CORS(app)

if __name__ == "__main__":
    # ...

    is_bootstrap = True
    if (is_bootstrap):
        # register bootstrap node in the ring
        node.register_node_to_ring(0, BOOTSTRAP_IP, BOOTSTRAP_PORT, node.wallet.public_key, 100 * number_of_nodes)

        # create the genesis block and add the first transaction to it
        node.create_genesis_block()
        first_transaction = Transaction(0, node.wallet.public_key, 100 * number_of_nodes, None, None)
        node.current_block.transactions.append(first_transaction)
        node.current_block.current_hash = node.current_block.calc_hash()
        node.wallet.transactions.append(first_transaction)

        # add genesis block to the chain
        node.chain.blocks.append(node.current_block)
        node.create_new_block()

        # listen in the specified address (ip:port)
        app.run(host=BOOTSTRAP_IP, port=BOOTSTRAP_PORT)
    else:
        # bootstrap node registers new node
        register_address = 'http://' + BOOTSTRAP_IP + ':' + BOOTSTRAP_PORT + '/register_node'

        def thread_function():
            time.sleep(2)
            response = requests.post(
                register_address,
                data={'public_key': node.wallet.public_key, 'ip': IPAddr, 'port': port}
            )

            if response.status_code == 200:
                print("Node initialized")

            node.id = response.json()['id']

        req = threading.Thread(target=thread_function, args=())
        req.start()

        # Listen in the specified address (ip:port)
        app.run(host=IPAddr, port=port)