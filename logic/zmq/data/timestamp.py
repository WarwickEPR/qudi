import time
import re
from tables.node import Node


class Timestamp:

    TIMESTAMP = re.compile(r"\d{8}_\d{6}")

    @classmethod
    def get_timestamp(cls):
        return time.strftime("%Y%m%d_%H%M%S", time.gmtime())

    @classmethod
    def extract_timestamp(cls, x):
        n = x
        if isinstance(x, Node):
            n = x._v_name

        m = re.search(cls.TIMESTAMP, n)
        if m:
            return m[0]
        else:
            return ''
