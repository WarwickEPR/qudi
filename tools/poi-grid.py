def make_poi_grid(prefix, A, B, C, nx, ny, mx, my):
    Ap = poimanagerlogic.get_poi_position(A)
    Bp = poimanagerlogic.get_poi_position(B)
    Cp = poimanagerlogic.get_poi_position(C)
    dX = (Bp-Ap)/(nx-1)
    dY = (Cp-Ap)/(ny-1)

    for i in range(mx):
        for j in range(my):
            poimanagerlogic.add_poi(position=Ap+i*dX+j*dY, name='{}_{}_{}'.format(prefix, i, j), emit_change=False)

    poimanagerlogic.sigRoiUpdated.emit({'pois': poimanagerlogic.poi_positions})