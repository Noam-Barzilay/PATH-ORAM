import random
from server import Block, Bucket
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def deserialize_block(block_data):
    """
    function to deserialize a block from bytes representation
    :param block_data: the bytes representation of the block's data
    :return: the deserialized block object
    """
    a = int.from_bytes(block_data[0:4], 'big')
    x = int.from_bytes(block_data[4:8], 'big')
    data = block_data[8:12].decode('utf-8')
    flag = block_data[12:13] == b'1'
    return Block(a, x, data, flag)


class Client:
    def __init__(self, server):
        # initialize empty stash
        self.stash = []
        # initialize position map, mapping each block to a random leaf
        self.position_map = {block: random.randint(0, pow(2, server.L) - 1) for block in range(server.N)}
        # generate key and cipher for each bucket in server's tree
        self.keys = [AESGCM.generate_key(128) for _ in range(server.num_of_buckets)]
        self.aesgcm_ciphers = [AESGCM(k) for k in self.keys]
        # store nonces per bucket (use to randomize the encryption)
        self.nonces = []
        # fills every bucket with encrypted dummy blocks and uploads them to the server
        for i in range(server.num_of_buckets):
            nonce = os.urandom(12)
            self.nonces.append(nonce)
            dummy_bucket = Bucket([], server.Z, server.N, True)
            # create string data to encrypt the blocks together
            data_to_encrypt = b"||".join([block.serialize() for block in dummy_bucket.blocks])
            # authentication based on bucket's number
            data_to_authenticate = f"bucket_{i}".encode('utf-8')
            # write to server
            server.tree[i] = self.aesgcm_ciphers[i].encrypt(nonce, data_to_encrypt, data_to_authenticate)

    def get_path_leaf_to_root(self, leaf_index, L):
        """
        Returns the path from the leaf node to the root in a full binary tree (array representation).

        Parameters:
        - leaf_index (int): The index of the leaf (0 to 2^L - 1).
        - L (int): The height (L) of the tree.

        Returns:
        - List[int]: The path from leaf to root in the array representation of the tree.
        """
        # Compute index of the leaf in the array representation
        total_nodes = pow(2, (L + 1)) - 1
        first_leaf_index = total_nodes - pow(2, L)
        i = first_leaf_index + leaf_index

        path = []
        while i >= 0:
            path.append(i)
            if i != 0:
                i = (i - 1) // 2  # Move to parent
            else:
                break

        return path

    def Access(self, op, a, data_, server):
        """
        :param op: type of desired operation
        :param a: identifier of data block
        :param data: data to write, None if op is read
        :return: the block's old data
        """

        """Remap block: Randomly remap the position of block a to a new random position (corresponding leaf)"""
        x = self.position_map[a]
        new_x = random.randint(0, pow(2, server.L) - 1)
        self.position_map[a] = new_x

        """Read the path P(x) containing block a"""
        i = 0
        for bit in str(bin(x))[2:].zfill(server.L):
            # read whole bucket (all blocks in it) to stash
            """decrypt bucket as a whole"""
            # use cipher to decrypt the encrypted bucket (server.tree[i]])
            cur_bucket_in_bytes = server.tree[i]
            data_to_authenticate = f"bucket_{i}".encode('utf-8')
            decrypted_bucket = self.aesgcm_ciphers[i].decrypt(self.nonces[i], cur_bucket_in_bytes, data_to_authenticate)
            # add blocks to stash
            self.stash += [deserialize_block(block) for block in decrypted_bucket.split(b"||")]
            if bit == '0':  # go to left child
                i = 2*i + 1
            else:  # go to right child
                i = 2*i + 2

        # add leaf bucket blocks to stash
        """decrypt leaf bucket as a whole"""
        cur_leaf_bucket_in_bytes = server.tree[i]
        data_to_authenticate = f"bucket_{i}".encode('utf-8')
        decrypted_leaf_bucket = self.aesgcm_ciphers[i].decrypt(self.nonces[i], cur_leaf_bucket_in_bytes, data_to_authenticate)
        # add blocks to stash
        self.stash += [deserialize_block(block) for block in decrypted_leaf_bucket.split(b"||")]

        # read block a from stash
        data = None
        block_idx = -1
        for block in self.stash:
            if block.a == a:
                block_idx = self.stash.index(block)
                data = block.data
                break

        """Update block: If the access is a write, update the data of block a"""
        if op == "write":
            if block_idx >= 0:
                self.stash[block_idx] = Block(a, new_x, data_, False)
            else:
                self.stash.append(Block(a, new_x, data_, False))
        # if op is delete, delete the block from stash
        elif op == "delete":
            self.stash.remove(self.stash[block_idx])

        """Write the path back to the server's tree storage"""
        # traversal from leaf to root, write each bucket exactly one time
        path_back = self.get_path_leaf_to_root(x, server.L)

        for level in range(len(path_back)):  # length is L
            blocks_to_add = []
            # check if non dummy block/s can be written at current level
            for block in self.stash:
                if block.dummy_flag == True:
                    continue
                else:
                    leaf = self.position_map[block.a]
                    # retrieve block's path
                    cur_block_path = self.get_path_leaf_to_root(leaf, server.L)
                    # if there is an intersection in the same level in the tree of the 2 paths
                    if cur_block_path[level] == path_back[level]:
                        # add block to bucket if there is enough space
                        if len(blocks_to_add) < server.Z:
                            blocks_to_add.append(block)
                        # else overflow to stash (block is already in stash)

            # pad bucket with dummy blocks
            num_of_dummies = server.Z - len(blocks_to_add)
            for _ in range(num_of_dummies):
                # add dummy block
                blocks_to_add.append(Block(server.N+1, 0, "----", True))

            """encrypt bucket as a whole"""
            # create new bucket
            new_bucket = Bucket(blocks_to_add, server.Z, server.N, False)
            # create new nonce
            new_nonce = os.urandom(12)
            self.nonces[path_back[level]] = new_nonce
            data_to_encrypt = b"||".join([block.serialize() for block in new_bucket.blocks])
            data_to_authenticate = f"bucket_{path_back[level]}".encode('utf-8')
            # write bucket to tree
            server.tree[path_back[level]] = self.aesgcm_ciphers[path_back[level]].\
                encrypt(new_nonce, data_to_encrypt, data_to_authenticate)

            # remove real added block/s from stash
            for block_ in blocks_to_add:
                if block_.dummy_flag == False:
                    self.stash.remove(block_)

        # clear stash of dummies
        self.stash = [block for block in self.stash if block.dummy_flag == False]

        return data

    def store_data(self, server, id, data):
        return self.Access("write", id, data, server)

    def retrieve_data(self, server, id):
        return self.Access("read", id, None, server)

    def delete_data(self, server, id, data):
        return self.Access("delete", id, data, server)
