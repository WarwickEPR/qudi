from tables import *


class ROI(IsDescription):
    name = StringCol(128, pos=0)  # limits POI name length but this is ample
    x = Float32Col(pos=1)
    y = Float32Col(pos=2)
    z = Float32Col(pos=3)

