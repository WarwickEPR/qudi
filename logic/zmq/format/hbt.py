from tables import *


class HBT(IsDescription):
    bin_times = Float32Col(pos=0)
    g2_raw = Float32Col(pos=1)
    g2_raw_normalized = Float32Col(pos=2)
