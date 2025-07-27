import math


class Block:
    """
    dummy block will have id of N+1 (non existing block)
    """
    def __init__(self, address, leaf_x, data, dummy_flag=False):
        self.a = address  # int
        self.x = leaf_x   # int
        self.data = data   # string with 4 characters
        self.dummy_flag = dummy_flag  # boolean flag
        self.metadata = [address, leaf_x, data, dummy_flag]

    def serialize(self):
        # Convert block to a fixed-length byte format
        flag = b'1' if self.dummy_flag else b'0'
        return (
                self.a.to_bytes(4, 'big') +
                self.x.to_bytes(4, 'big') +
                self.data.encode('utf-8') +
                flag
        )


class Bucket:
    """
    bucket looks like [block1||block2||block3||block4] after serialization before encryption
    """
    def __init__(self, blocks, bucket_size, num_of_blocks, empty=True):
        # initialize full bucket with dummy blocks
        self.size = bucket_size
        if empty:
            # initialize with dummy blocks
            self.blocks = [Block(num_of_blocks+1, 0, "----", True) for _ in range(bucket_size)]
        else:
            # initialize with given blocks
            self.blocks = [block for block in blocks]


class Server:
    def __init__(self, N, Z=4):
        self.N = N
        self.Z = Z
        self.num_of_buckets = int(N / Z)
        self.L = math.ceil(math.log(self.num_of_buckets, 2)) - 1
        # initialize tree as flat array
        self.tree = [Bucket([], self.Z, N, True) for _ in range(self.num_of_buckets)]
