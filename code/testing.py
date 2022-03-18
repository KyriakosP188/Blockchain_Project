from argparse import ArgumentParser
from threading import Thread
import requests
import pickle
import config

LIMIT = None

def thread_function(i, number_of_nodes, responses):
    with open(f'../transactions/{number_of_nodes}nodes/transactions{i}.txt', 'r') as f:
        count = 0
        for line in f:
            id, amount = line.split(' ')
            id = int(id[2])
            amount = int(amount)
            response = requests.post('http://' + config.BOOTSTRAP_IP + ':500' + str(i) + '/create_new_transaction',
                                    data=pickle.dumps((id, amount)))
            responses.append(response)
            count += 1
            if LIMIT and count > LIMIT:
                break

if __name__ == "__main__":
    parser = ArgumentParser(description='Testing the noobcash system.')
    parser.add_argument('-n',
                        '--nodes',
                        type=int,
                        help='The number of nodes in the blockchain.',
                        required=True)

    args = parser.parse_args()
    number_of_nodes = args.nodes
    if number_of_nodes != 5 and number_of_nodes != 10:
        print('Please use 5 or 10 nodes.')
        exit()

    threads = []
    responses = []
    for i in range(number_of_nodes):
        thread = Thread(target=thread_function, args=(i, number_of_nodes, responses))
        threads.append(thread)
        thread.start()

    print('Testing has started.')

    for t in threads:
        t.join()

    print('Testing completed successfully.')