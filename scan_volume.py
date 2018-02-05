
trk = 'poi_20180125_2341_00_747335'
scn = 'poi_20180125_2343_06_553046'

def finished_image():
    scannerlogic.save_xy_data()

def refocus():
    poimanagerlogic.optimise_poi(trk)

def next_image():
    [x,y,z] = poimanagerlogic.get_poi_position(scn)
    if z > 168e-6:
        z = z - 200e-9
        poimanagerlogic.move_coords(scn, [x, y, z])
        poimanagerlogic.go_to_poi(scn)
        x0 = x - 50e-6
        x1 = x0 + 90e-6
        y0 = y - 55e-6
        y1 = y0 + 90e-6

        # so as to also display, change bounds of scan at the UI level & send down
        confocal._mw.x_min_InputWidget.setValue(x0)
        confocal._mw.x_max_InputWidget.setValue(x1)
        confocal._mw.y_min_InputWidget.setValue(y0)
        confocal._mw.y_max_InputWidget.setValue(y1)
        confocal.change_x_image_range()
        confocal.change_y_image_range()

        scannerlogic.start_scanning()

scannerlogic.signal_stop_scanning.connect(finished_image)
scannerlogic.signal_xy_data_saved.connect(refocus)
optimizerlogic.sigRefocusFinished.connect(next_image)