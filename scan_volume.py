
#trk = 'poi_20180125_2341_00_747335'
trk = 'guide'
#scn = 'poi_20180125_2343_06_553046'
scn = 'scn'

def finished_image():
    scannerlogic.save_xy_data()

def refocus():
    trkpoi = poimanagerlogic.poi_lookup['guide']
    poimanagerlogic.optimise_poi(trkpoi)

def next_image():
    scnpoi = poimanagerlogic.poi_lookup['scn']
    [x, y, z] = poimanagerlogic.get_poi_position(scnpoi)
    if z > 115e-6:
        z = z - 300e-9
        poimanagerlogic.move_coords(scnpoi, [x, y, z])
        poimanagerlogic.go_to_poi(scnpoi)
        x0 = x - 170.3e-6 + 125e-6
        x1 = x0 + 80e-6
        y0 = y - 98.7e-6 + 95e-6
        y1 = y0 + 65e-6

        # so as to also display, change bounds of scan at the UI level & send down
        confocal._mw.x_min_InputWidget.setValue(x0)
        confocal._mw.x_max_InputWidget.setValue(x1)
        confocal._mw.y_min_InputWidget.setValue(y0)
        confocal._mw.y_max_InputWidget.setValue(y1)
        confocal.change_x_image_range()
        confocal.change_y_image_range()

        scannerlogic.start_scanning()

def disconnect_volume_scan():
    scannerlogic.signal_stop_scanning.disconnect(finished_image)
    scannerlogic.signal_xy_data_saved.disconnect(refocus)
    optimizerlogic.sigRefocusFinished.disconnect(next_image)

def connect_volume_scan():
    scannerlogic.signal_stop_scanning.connect(finished_image)
    scannerlogic.signal_xy_data_saved.connect(refocus)
    optimizerlogic.sigRefocusFinished.connect(next_image)