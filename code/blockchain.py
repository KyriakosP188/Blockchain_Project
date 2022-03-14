from block import Block

class Blockchain:
    def __init__(self):
        # blockchain initialization
        self.blocks = []

    def add_block(self, block):
        # adds new validated block to the chain
        if self.validate_block(block):
            self.blocks.append(block)
            return True
        return False

    def validate_block(self, block):
        # checks if a certain block of the chain is valid
        return block.current_hash == block.calc_hash() and block.previous_hash == self.blocks[block.index - 1].current_hash

    def validate_chain(self):
        # checks if the chain is valid
        for block in self.blocks[1:]:
            if not self.validate_block(block):
                return False
        return True