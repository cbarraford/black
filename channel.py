import hashlib
from time import time
from urllib.parse import urlparse
import json
import requests

class Channel:
    def __init__(self, name):
        self.name = name
        self.created_at = time()
        self.ref = hashlib.sha256(f"{name} {self.created_at}".encode('utf-8')).hexdigest()
        self.chain = ChannelChain()


class ChannelChain:
    def __init__(self):
        self.current_msgs = []
        self.chain = []
        self.nodes = set()

        # Create the genesis block
        self.new_block(previous_hash=1, proof=100)

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'created_at': time(),
            'messages': self.current_msgs,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Reset the current list of transactions
        self.current_msgs = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, msg):
        self.current_msgs.append({
            'sender': sender,
            'msg': msg,
        })

        return self.last_block['index'] + 1

    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    def valid_chain(self, chain):
        # TODO we should validate also that the chain given is the same chain as we already have.
        # Otherwise a foreign node can create an entire new chain from scratch and replace all
        # messages with new messages (as long as the fake chain is longer than the current).
        # But this may no longer be an issue with signed messages or changing the consensus to
        # something like Proof of Authority
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            # Check that the hash of the block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check that the Proof of Work is correct
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        neighbours = self.nodes
        new_chain = None

        # We're only looking for chains longer than ours
        max_length = len(self.chain)

        # Grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if the length is longer and the chain is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # Replace our chain if we discovered a new, valid chain longer than ours
        if new_chain:
            self.chain = new_chain
            return True

        return False

    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:1] == "0"

    @property
    def last_block(self):
        # Returns the last Block in the chain
        return self.chain[-1]

    @staticmethod
    def hash(block):
        # We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()


