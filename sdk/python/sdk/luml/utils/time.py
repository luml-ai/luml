from time import time


def get_epoch() -> int:
    return int(time() * 1000)
