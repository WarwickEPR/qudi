import time
import re


def get_timestamp():
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


TIMESTAMP = re.compile(r"\d{8}_\d{6}")


def extract_timestamp(cls, x):
    m = re.search(cls.TIMESTAMP, x)
    if m:
        return m[0]
    else:
        return ''
