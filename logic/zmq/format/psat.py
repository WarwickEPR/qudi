from tables import *


class Psat(IsDescription):
    power = Float32Col(pos=0)
    count_rate = Float32Col(pos=1)

