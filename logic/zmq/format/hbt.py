from tables import *


class HbtTable(IsDescription):
    bin_times = Float32Col(pos=0)
    g2_raw = Float32Col(pos=1)
    g2_raw_normalized = Float32Col(pos=2)
