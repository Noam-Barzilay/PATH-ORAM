import math

N = 60  # blocks outsourced to server
Z = 4   # Capacity of each bucket (in blocks)
NUM_OF_BUCKETS = math.floor(N / Z)
L = math.floor(math.log(NUM_OF_BUCKETS, 2))  # Height of binary tree
