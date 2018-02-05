
import numpy as np
import time
import datetime
import qtpy.QtCore
import contextlib

# should really run when Qudi is restarted
import csv
import TimeTagger as tt

tagger = timetaggerSlow._tagger

# https://www.jdreaver.com/posts/2014-07-03-waiting-for-signals-pyside-pyqt.html
@contextlib.contextmanager
def wait_signal(signal, timeout=10000):
    """Block loop until signal emitted, or timeout (ms) elapses."""
    loop = qtpy.QtCore.QEventLoop()
    signal.connect(loop.quit)

    yield

    if timeout is not None:
        qtpy.QtCore.QTimer.singleShot(timeout, loop.quit)
    loop.exec_()

def scanv(v):
    nicard.set_up_scanner_clock()
    nicard.set_up_scanner()
    o = nicard.scan_voltage(v)
    nicard.close_scanner()
    nicard.close_scanner_clock()
    d = np.append(o, [])
    return d

def power_est(v):
    return (0.0166 * v - 0.0522) * 40

def fit_psat_aom(v,d):
    model, param = fitlogic.make_hyperbolicsaturation_model()
    param['I_sat'].min = 0
    param['I_sat'].max = 1e6
    param['I_sat'].value=max(d)*.7
    param['P_sat'].max = 10.0
    param['P_sat'].min = 0.0
    param['P_sat'].value = 4.0
    param['slope'].min = 0.0
    param['slope'].value=1e3
    param['offset'].min = 0.0
    r = fitlogic.make_hyperbolicsaturation_fit(x_axis=v, data=d, estimator=fitlogic.estimate_hyperbolicsaturation,
                                           add_params=param)
    return r

def fit_psat_power(p,d):
    model, param = fitlogic.make_hyperbolicsaturation_model()
    param['I_sat'].min = 0
    param['I_sat'].max = 1e6
    param['I_sat'].value=max(d)*.7
    param['P_sat'].max = 10.0
    param['P_sat'].min = 0.0
    param['P_sat'].value = 4.0
    param['slope'].min = 0.0
    param['slope'].value=1e3
    param['offset'].min = 0.0
    r = fitlogic.make_hyperbolicsaturation_fit(x_axis=p, data=d, estimator=fitlogic.estimate_hyperbolicsaturation,
                                           add_params=prm)
    return r

def refocus():
    pos = nicard.get_scanner_position()
    optimizerlogic.start_refocus(pos)
    while optimizerlogic.module_state.current == 'locked':
        time.sleep(0.2)


def run_hbt_with_refocus(p,t):
    timeBin = 500
    noBins = 2000
    # zero point happens in the middle of the plot
    maxTime = ((noBins * timeBin) / 2) / 1e3
    minTime = -maxTime
    # make the row for the time bins
    timeRow = np.linspace(minTime, maxTime, (noBins + 1))

    # start the correlation (iterate start stop just to clear last if not a fresh reload)
    coin = tt.Correlation(tagger, 0, 1, binwidth=timeBin, n_bins=noBins)
    coin.stop()
    coin.clear()

    go_to_poi(p)
    coin.start()
    time.sleep(t)
    data = coin.getData()
    coin.stop()
    go_to_poi(p)
    coin.start()
    time.sleep(t)

    with open(r"C:\Users\Confocal\Desktop\g2data-{}.csv".format(p), 'w', newline='') as csvfile:
        g2writer = csv.writer(csvfile)
        g2writer.writerows([timeRow, coin.getData()])
        g2writer.writerows([timeRow, data])

    coin.stop()
    coin.clear()

def run_hbt(poi,t):
    timeBin = 500
    noBins = 2000
    # zero point happens in the middle of the plot
    maxTime = ((noBins * timeBin) / 2) / 1e3
    minTime = -maxTime
    # make the row for the time bins
    timeRow = np.linspace(minTime, maxTime, (noBins + 1))

    go_to_poi(poi)


    # start the correlation (iterate start stop just to clear last if not a fresh reload)
    coin = tt.Correlation(tagger, 0, 1, binwidth=timeBin, n_bins=noBins)
    coin.stop()
    coin.clear()
    coin.start()
    time.sleep(t)

    with open(r"C:\Users\Confocal\Desktop\g2data-{}.csv".format(poi), 'w', newline='') as csvfile:
        g2writer = csv.writer(csvfile)
        g2writer.writerows([timeRow, coin.getData()])
    coin.stop()
    coin.clear()

v = np.linspace(3.0, 7.0, 25)

psat_data = {}
psat_fit = {}
psat_v = {}


def go_to_poi(p):
    poimanagerlogic.optimise_poi(p)
    while optimizerlogic.module_state.current != 'idle':
        time.sleep(1)

#https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(l,n):
    for i  in range(1,len(l),n):
        yield l[i:i+n]

def wait_for_refocus():
    while optimizerlogic.module_state.current == 'locked':
        time.sleep(0.2)

#def wait_for_refocus():
#    wait_signal(optimizerlogic.sigRefocusFinished)

def refine_poi_list():
    pois = poimanagerlogic.get_all_pois()
    pois = pois[1:-1] # skip the special ones
    refpoi = pois[0]
    for c in chunks(pois, 5):
        poimanagerlogic.optimise_poi(refpoi)  # update reference position and sample position
        wait_for_refocus()
        for poi in c:
            optimizerlogic.start_refocus(poimanagerlogic.get_poi_position(poi))
            wait_for_refocus()
            newpos = poimanagerlogic._confocal_logic.get_position()[:3]
            poimanagerlogic.move_coords(poi,newpos)

def iterate_over_poi_hbt(poi,v):
    with open(r"C:\Users\Confocal\Desktop\positions-long.txt", 'w', 1) as positions_file:
        positions = csv.writer(positions_file)

        for p in poi:
            print('Going to {}'.format(p))
            go_to_poi(p)
            positions.writerow([ p,
                                 optimizerlogic.optim_pos_x,
                                 optimizerlogic.optim_sigma_x,
                                 optimizerlogic.optim_pos_y,
                                 optimizerlogic.optim_sigma_y,
                                 optimizerlogic.optim_pos_z,
                                 optimizerlogic.optim_sigma_z
                                 ])
            d = scanv(v)
            powers = power_est(v)
            psat_data[p] = d
            fit = fit_psat_aom(v-3,d)
            psat_fit[p] = fit
            vsat = fit.best_values['P_sat'] + 3.0
            psat_v[p] = vsat
            summary = "# Isat {} counts at\n# {} V\n# {} mW\n# fit {}\n\n".format(fit.best_values['I_sat'],vsat,power_est(vsat),fit.best_values)
            print('fitted Isat {} at {}V {}mW'.format(fit.best_values['I_sat'],vsat,power_est(vsat)))

            with open(r"C:\Users\Confocal\Desktop\psat-{}.csv".format(p), 'w', newline='') as csvfile:
                csvfile.write(summary)
                pwriter = csv.writer(csvfile)
                pwriter.writerows([v, powers, d, fit.best_fit])

            print('Done Psat {}'.format(p))

            if vsat > 7.0:
                V = 7.0
            else:
                V = vsat
            nicard.set_voltage(V)
            run_hbt(p,300)
            print('Done HBT {}'.format(p))

def iterate_over_poi_psat_only(poi,v):
    with open(r"C:\Users\Confocal\Desktop\positions.txt", 'w',0) as positions_file:
        positions = csv.writer(positions_file)
        for p in poi:
            print('Going to {}'.format(p))
            go_to_poi(p)
            positions.writerow([ optimizerlogic.optim_pos_x,
                                 optimizerlogic.optim_sigma_x,
                                 optimizerlogic.optim_pos_y,
                                 optimizerlogic.optim_sigma_y,
                                 optimizerlogic.optim_pos_z,
                                 optimizerlogic.optim_sigma_z
                                 ])
            d = scanv(v)
            powers = power_est(v)
            psat_data[p] = d
            fit = fit_psat_aom(v-3,d)
            psat_fit[p] = fit
            vsat = fit.best_values['P_sat'] + 3.0
            psat_v[p] = vsat
            summary = "# Isat {} counts at\n# {} V\n# {} mW\n# fit {}\n\n".format(fit.best_values['I_sat'],vsat,power_est(vsat),fit.best_values)
            print('fitted Isat {} at {}V {}mW'.format(fit.best_values['I_sat'],vsat,power_est(vsat)))

            with open(r"C:\Users\Confocal\Desktop\psat-{}.csv".format(p), 'w', newline='') as csvfile:
                csvfile.write(summary)
                pwriter = csv.writer(csvfile)
                pwriter.writerows([v, powers, d, fit.best_fit])

            print('Done Psat {}'.format(p))

def timestamp():
    return datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H-%M-%S')

def psat_and_set(v):
    psatd = scanv(v)
    powers = power_est(v)
    fit = fit_psat_aom(v-3,psatd)
    psatfit = fit
    vsat = fit.best_values['P_sat'] + 3.0
    summary = "# Isat {} counts at\n# {} V\n# {} mW\n# fit {}\n\n".format(fit.best_values['I_sat'],vsat,power_est(vsat),fit.best_values)
    print('fitted Isat {} at {}V {}mW'.format(fit.best_values['I_sat'],vsat,power_est(vsat)))

    ts = timestamp()

    with open(r"C:\Users\Confocal\Desktop\psat-{}.csv".format(ts), 'w', newline='') as csvfile:
        csvfile.write(summary)
        pwriter = csv.writer(csvfile)
        pwriter.writerows([v, powers, psatd, fit.best_fit])

        print('Done PSat')

        if vsat > 7.0:
            V = 7.0
        else:
            V = vsat
        nicard.set_voltage(V)
