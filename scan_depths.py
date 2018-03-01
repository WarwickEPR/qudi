
depth = [164.6, 163, 161.2]
global layer
layer = 0

def finished_image():
    scannerlogic.save_xy_data()

def next_image():
    global layer
    if layer < len(depth):
        Z = depth[layer] * 1e-6
        layer += 1
        scannerlogic.set_position("", z=Z)
        scannerlogic.start_scanning()

scannerlogic.signal_stop_scanning.connect(finished_image)
scannerlogic.signal_xy_data_saved.connect(next_image)
