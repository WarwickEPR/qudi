
global depths
depths = []
global layer
layer = 0

def finished_image():
    scannerlogic.save_xy_data()

def next_image():
    global layer
    global depths
    if layer < len(depths):
        Z = depths[layer] * 1e-6
        layer += 1
        scannerlogic.set_position("", z=Z)
        scannerlogic.start_scanning()

def setup_depth_scans(depth_list):
  global depths
  depths = depth_list
  global layer
  layer = 0
  scannerlogic.signal_stop_scanning.connect(finished_image)
  scannerlogic.signal_xy_data_saved.connect(next_image)

def stop_depth_scans():
    global layer
    layer = 99999
    scannerlogic.signal_stop_scanning.disconnect()
    scannerlogic.signal_xy_data_saved.disconnect()
