from tables import *
import numpy as np


class ROI:

    root = '/ROI'
    version = 'ROI_v1.0'

    class Description(IsDescription):
        name = StringCol(128, pos=0)  # limits POI name length but this is ample
        x = Float32Col(pos=1)
        y = Float32Col(pos=2)
        z = Float32Col(pos=3)


class TiltCorrection:

    def __init__(self, pivot=(0, 0, 0), phi=0, psi=0):
        self.translation = np.array([*pivot])
        self.rotation_x = np.array([[1, 0, 0],
                                    [0, np.cos(phi), -np.sin(phi)],
                                    [0, np.sin(phi), np.cos(phi)]])
        self.rotation_y = np.array([[np.cos(psi), 0, np.sin(psi)],
                                    [0, 1, 0],
                                    [-np.sin(psi), 0, np.cos(psi)]])
        self.rotation = self.rotation_y * self.rotation_x

    def rotate(self, point):

        # translate origin
        p = np.array([*point]) - self.translation

        # apply rotation
        q = self.rotation * p

        # translate origin back
        return q + self.translation


class Rotation:

    def __init__(self, pivot=(0,0), theta=0):
        self.pivot = pivot
        self.theta = theta


class RoiExtract:

    def __init__(self, table: Table):
        self.table = table,

    def pois(self, x_min=-np.inf, x_max=np.inf, y_min=-np.inf, y_max=np.inf, z_min=-np.inf, z_max=np.inf, rotation=None):
        pois = dict()

        for row in self.table:
            x = row['x']
            y = row['y']
            z = row['z']

            if rotation:
                x_orig, y_orig, z_orig = x, y, z
                x, y, z = rotation.rotate(x, y, z)

            if x < x_min: continue
            if x > x_max: continue
            if y < y_min: continue
            if y > y_max: continue
            if z < z_min: continue
            if z > z_max: continue
            pois[row['name]']] = (x, y, z)
        return pois

    # Return a copy rotated into another coordinate system
    def rotate(self, pivot, xy_norm, rotation):
        pass

