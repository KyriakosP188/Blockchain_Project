from argparse import ArgumentParser
from threading import Thread
import requests
import pickle
import config
import random
import time

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
            time.sleep(random.random() * 10)

if __name__ == "__main__":
    parser = ArgumentParser(description='Testing the noobcash system.')
    parser.add_argument('-n',
                        '--nodes',
                        type=int,
                        help='The number of nodes in the blockchain.',
                        required=True)
    parser.add_argument('-d',
                        '--difficulty',
                        type=int,
                        help='The mining difficulty of a new block.',
                        required=True)
    parser.add_argument('-c',
                        '--capacity',
                        type=int,
                        help='The transaction capacity of a block.',
                        required=True)

    args = parser.parse_args()
    number_of_nodes = args.nodes
    difficulty = args.difficulty
    capacity = args.capacity
    if number_of_nodes != 5 and number_of_nodes != 10:
        print('Please use 5 or 10 nodes.')
        exit()

    threads = []
    responses = []
    for i in range(number_of_nodes):
        thread = Thread(target=thread_function, args=(i, number_of_nodes, responses))
        threads.append(thread)
        thread.start()

    folder = f'{number_of_nodes}-{difficulty}-{capacity}'
    target = f'start_time-{number_of_nodes}-{difficulty}-{capacity}.txt'
    with open('../../logs/' + folder + '/' + target, 'a') as file:
        file.write(str(time.time()) + '\n')
    print('Testing has started.')

    for t in threads:
        t.join()

    print('Testing completed successfully.')