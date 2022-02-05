from tables import *


# General form for an arbitrary NI controlled, image scan.
# Point in any order, with or without transformed coordinates
# see attributes for which interpretation to use
# (this may be interpreted more simply if the scan pattern is known)
class ScanData(IsDescription):
    x = Float32Col(pos=0)
    y = Float32Col(pos=1)
    z = Float32Col(pos=2)
    a = Float32Col(pos=3)
    ch1 = Float32Col(pos=4)
    ch2 = Float32Col(pos=5)

# 2D image slices in parametric coordinates are stored as gzip compressed arrays