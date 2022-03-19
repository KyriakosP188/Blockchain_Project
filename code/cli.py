from transaction import Transaction
import pyfiglet
import requests
import pickle
import cmd

class Noobcash(cmd.Cmd):
    intro = '\nWelcome to the noobcash client. Type help or ? to list commands.\n'
    prompt = 'noobcash> '

    def preloop(self):
        print(pyfiglet.figlet_format('noobcash'))
        self.port = input('Enter the port of your wallet: ')
        self.ip = '127.0.0.1'

    def do_t(self, args):
        't <recipient_id> <amount>\nSend the specified amount of NBC coins to the wallet of the node with the given ID.'
        args = args.split(' ')
        if len(args) != 2:
            print('Please provide <recipient_id> and <amount> to create the transaction.')
            return
        try:
            response = requests.post('http://' + self.ip + ':' + self.port + '/create_new_transaction',
                                    data=pickle.dumps((int(args[0]), int(args[1]))))
            if response.status_code == 200:
                print(f'Transaction of {args[1]} NBC coins to node{args[0]} completed successfully.')
            elif response.status_code == 402:
                print(response.json()['message'])
            elif response.status_code == 403:
                print(response.json()['message'])
            elif response.status_code == 404:
                print(response.json()['message'])
            else:
                print('Transaction failed. Check recipient ID or the system may be down.')
        except:
            print('Connection failed.')

    def do_view(self, _):
        'View the transactions of the current last block of the blockchain.'
        try:
            response = requests.get('http://' + self.ip + ':' + self.port + '/view_last_transactions')
            transactions = pickle.loads(response._content)
            for i in range(len(transactions)):
                print('Transaction', i)
                print('Sender Address:')
                print(transactions[i].sender_address)
                print('Recipient Address:')
                print(transactions[i].receiver_address)
                print('Amount:', transactions[i].amount)
                print('ID:', transactions[i].transaction_id)
                if i != len(transactions) - 1:
                    print('')
        except:
            print('Connection failed.')

    def do_balance(self, _):
        'Check your wallet balance.'
        try:
            response = requests.get('http://' + self.ip + ':' + self.port + '/get_balance')
            (balance, ring) = pickle.loads(response._content)
            print(f'You have {balance} NBC coins in your wallet.')
            for node in ring:
                print(f"Node{node['id']} has {node['balance']} NBC coins in their wallet.")
        except:
            print('Connection failed.')

    def do_exit(self, _):
        'Exit the noobcash client.'
        return True

if __name__ == "__main__":
    Noobcash().cmdloop()