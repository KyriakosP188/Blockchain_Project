from flask import Blueprint
from node import Node

node = Node()
number_of_nodes = 0
rest_api = Blueprint('rest_api', __name__)

# ------------------------------------------
# ------------- Node endpoints -------------
# ------------------------------------------

@rest_api.route('/register_node', methods=['POST'])
def register_node():
    # registers node to the ring (only called by bootstrap node)


@rest_api.route('/validate_transaction', methods=['POST'])
def validate_transaction():
    # validates incoming transaction


@rest_api.route('/add_transaction_to_block', methods=['POST'])
def add_transaction_to_block():
    # adds transaction to the current block of the chain


@rest_api.route('/add_block_to_chain', methods=['POST'])
def add_block_to_chain():
    # adds completed block to the chain


@rest_api.route('/get_chain', methods=['GET'])
def get_chain():
    # sends chain of this node


# ------------------------------------------
# -------------- CLI endpoints -------------
# ------------------------------------------

@rest_api.route('/create_new_transaction', methods=['POST'])
def create_new_transaction():
    # creates new transaction


@rest_api.route('/view_last_transactions', methods=['GET'])
def view_last_transactions():
    # returns the transactions that are in the last validated block of the chain


@rest_api.route('/get_balance', methods=['GET'])
def get_balance():
    # returns the balance of this node's wallet
