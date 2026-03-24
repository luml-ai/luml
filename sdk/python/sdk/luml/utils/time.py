import time


def get_epoch() -> int:
    return int(time.time() * 1000)
