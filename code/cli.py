from transaction import Transaction
import pyfiglet
import requests
import pickle
import cmd

class Noobcash(cmd.Cmd):
    intro = 'Welcome to the noobcash client. Type help or ? to list commands.\n'
    prompt = 'noobcash>'

    def preloop(self):
        print(pyfiglet.figlet_format('noobcash'))
        port = input('\nEnter the port of your wallet: ')
        ip = 'localhost'

    def do_t(self, args):
        't <recipient_address> <amount>\nSend the specified amount of NBC coins to the wallet of the given address.\n'
        args = args.split(' ')
        if len(args) != 2 or not isinstance(args[1], int):
            print('Please provide correct <recipient_address> and <amount> to create the transaction.')
            return
        response = requests.post('http://' + ip + ':' + port + '/create_new_transaction',
								data=pickle.dumps((args[1], args[0])))
        if response.status_code == 200:
            print(f'Transaction of {args[1]} NBC coins to {args[0]} completed successfully.')
        elif response.status_code == 402:
            print(response.json()['message'])
        else:
            print('Transaction failed. Check reciepent address or the system may be down.')

    def do_view(self, _):
        'view\nView the transactions of the current last block of the blockchain.'
        response = requests.get('http://' + ip + ':' + port + '/view_last_transactions')
        transactions = pickle.loads(response._content)
        for i in range(len(transactions)):
            print('Transaction', i)
            print('Sender Address:', transactions[i].sender_address)
            print('Recipient Address:', transactions[i].receiver_address)
            print('Amount:', transactions[i].amount)
            print('ID:', transactions[i].transaction_id)
            if i != len(transactions) - 1:
                print('')

    def do_balance(self, _):
        'balance\nCheck your wallet balance.'
        response = requests.get('http://' + ip + ':' + port + '/get_balance')
        balance = pickle.loads(response._content)
        print(f'You have {balance} NBC coins in your wallet.')

    def do_exit(self, _):
        'exit\nExit the noobcash client.'
        return True

if __name__ == "__main__":
    Noobcash().cmdloop()