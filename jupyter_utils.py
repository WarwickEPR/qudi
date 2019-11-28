
import time
import datetime
import numpy as np
import matplotlib.pyplot as plt
import json
import os

log_file = os.path.join(working_directory, 'out.log')
record_file_abs = os.path.join(working_directory, record_file)

def timestr():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def progress(msg):
    out = timestr() + ' ' + msg
    with open(log_file, 'a') as f:
        f.write(out + '\n')
    print(out)

def mkdir_working(basedir, subdirs):
    try:
        progress('mkdir {}'.format(basedir))
        os.mkdir(basedir)
    except FileExistsError:
        pass

    for d in subdirs:
        try:
            d = os.path.join(basedir, d)
            progress('mkdir {}'.format(d))
            os.mkdir(d)
        except FileExistsError:
            pass

# set up a dictionary to accumulate useful observations on the fly
def setup_recording(record_file_abs):
    if os.path.isfile(record_file_abs):
        with open(record_file_abs) as rf:
            acc = json.load(rf)
    else:
        acc = dict()
    return acc

mkdir_working(working_directory, ['img','interim'])
acc = setup_recording(record_file_abs)


def check_ok_to_go():
    if os.path.isfile(os.path.join(working_directory, 'GO')) and not os.path.isfile(os.path.join(working_directory, 'STOP')):
        return True


def save_acc_record():
    backup_dir = os.path.join(working_directory, 'interim')
    if os.path.isfile(record_file_abs):
        # just in case, hold on to the superceded ones
        try:
            os.mkdir(backup_dir)
        except FileExistsError:
            pass

        backup_file = os.path.join(backup_dir, record_file + '_' + timestr())
        try:
            os.rename(record_file_abs, backup_file)
        except FileExistsError:
            pass  # we've just done this! no point

    with open(record_file_abs, 'w') as f:
        json.dump(acc, f)


def ensure_logic_started(module_list):
    # requires these modules to be preloaded
    for m in module_list:
        if not manager.isModuleLoaded('logic',m):
            print('{} is not loaded, starting'.format(m))
            manager.startModule('logic',m)

ensure_logic_started(['aomlogic','hbtlogic','counterlogic','poimanagerlogic','pulsedmasterlogic'])


def plot_image(xy_data, filename):
    fig, ax = plt.subplots()
    X = xy_data[:,:,0]*1e6
    Y = xy_data[:,:,1]*1e6
    A = xy_data[:,:,3]
    ax.set_xlabel('X (um)')
    ax.set_ylabel('Y (um)')
    psm = ax.pcolormesh(X,Y, A, cmap='inferno')
    fig.colorbar(psm, ax=ax)
    plt.savefig(filename)
    plt.close(fig)

def clear_flag(x):
    notifications[x] = False


def wait_for(x, check_period=2, time_limit=3600):
    waited_time = 0

    while not stop and not move_on:
        if notifications.get(x, False):
            # relies on the notifications[x] being clear before loop is
            # first entered just in case the thing was done instantly
            # Clear here for convenience. To be sure clear explicitly before
            # setting off the process that you're waiting on
            notifications[x] = False
            return True
        else:
            time.sleep(check_period)
            waited_time += check_period
            if waited_time > time_limit:
                progress("Waited {} s - moving on".format(waited_time))
                return False
            else:
                pass


def load_list(poi_file):
    with open(poi_file) as f:
        y = list(filter(None,[x.strip() for x in f]))
    return y


def start_poi_record(poi):
    acc[poi] = {'starttime': timestr()}
    save_acc_record()


def update_poi_record(poi, u):
    if poi not in acc:
        acc[poi] = {'starttime': timestr()}
    acc[poi]['latesttime'] = timestr()
    acc[poi].update(u)
    save_acc_record()


# transform a fit parameters object into a simple dictionary that can be serialised
def extract_fit_parameters(prefix, parameters):
    t = dict()
    for (k, p) in parameters.items():
        v = p.value
        err = p.stderr
        t['_'.join([prefix, k])] = v
        t['_'.join([prefix, k, 'err'])] = err
    return t


def revisit_guide(guide):
    # refocus on the guide point
    progress('Tracking guide point {}'.format(guide))
    clear_flag('refocus done')
    poimanagerlogic.optimise_poi_position(name=guide, update_roi_position=True)
    wait_for('refocus done', time_limit=30)
    progress('New guide position is {}'.format(poimanagerlogic.get_poi_position(guide) * 1e6))
    time.sleep(1)


def refocus(poi, save_image=False):
    progress('Refocusing on {}'.format(poi))
    clear_flag('refocus done')
    poimanagerlogic.optimise_poi_position(name=poi, update_roi_position=False)
    wait_for('refocus done', time_limit=30)
    poimanagerlogic.set_active_poi(poi)
    poimanagerlogic.save_roi()
    if save_image:
        plot_image(optimizerlogic.xy_refocus_image, os.path.join(working_directory, 'img', 'opt_' + poi + '.png'))
    progress('Updated poi {} to {}'.format(poi, poimanagerlogic.get_poi_position(poi) * 1e6))
    time.sleep(1)


def psat(poi):
    progress('Running Psat on {}'.format(poi))
    clear_flag('psat fit done')
    aomlogic.run_psat()  # automatically runs a fit
    wait_for('psat fit done', check_period=1, time_limit=6)
    update_poi_record(poi,
                      {'laser_power': aomlogic.get_power(), 'Psat': aomlogic.fitted_Psat, 'Isat': aomlogic.fitted_Isat,
                       'Isat_offset': aomlogic.fitted_offset})
    clear_flag('psat saved')
    aomlogic.save_psat()
    wait_for('psat saved', check_period=1, time_limit=6)
    progress('Psat complete on {}'.format(poi))
    time.sleep(1)


def hbt(poi):
    progress('Running HBT on {}'.format(poi))
    hbtlogic.start_hbt()
    doze(HBT_DURATION)
    hbtlogic.stop_hbt()
    hbtlogic.save_hbt()
    progress('HBT complete on {} (fit omitted)'.format(poi))
    time.sleep(1)


def hbt_withcountrate(poi):
    progress('Running HBT+counts on {}'.format(poi))
    hbtlogic.start_hbt()
    counterlogic.start_saving()
    time.sleep(HBT_DURATION)
    hbtlogic.stop_hbt()
    hbtlogic.save_hbt()
    cdata, cparam = counterlogic.save_data()
    counts = [x[1] for x in cdata]
    mean_counts = np.mean(counts)
    update_poi_record(poi, {'mean_counts': mean_counts})
    progress('HBT complete on {} (fit omitted)'.format(poi))
    time.sleep(1)

def mean_counts(poi):
    # Use the counterlogic as it's running (could do any duration with TimeTagger)
    progress('Getting mean countrate {}'.format(poi))
    window_length = counterlogic.get_count_length() / counterlogic.get_count_frequency()
    time.sleep(window_length + 1)
    return np.mean(counterlogic.countdata)

def odmr(poi):
    progress('Running ODMR on {}'.format(poi))
    odmrlogic.start_odmr_scan()
    time.sleep(5)
    odmrlogic.do_fit(None)
    # ensure we've started
    wait_for('odmr output change')
    odmrlogic.do_fit('Lorentzian dip')
    odmrlogic.save_odmr_data()
    update_poi_record(poi, {'odmr_one_dip': odmrlogic.fc.current_fit_result.best_values})
    # add the confidence interval another time!
    time.sleep(5)
    odmrlogic.do_fit('Two Lorentzian dips')
    odmrlogic.save_odmr_data()
    update_poi_record(poi, {'odmr_two_dip': odmrlogic.fc.current_fit_result.best_values})
    time.sleep(2)


def start_tracking(poi):
    progress("Starting tracking {}".format(poi))
    poimanagerlogic.set_active_poi(poi)
    clear_flag("refocus done")
    if poimanagerlogic.module_state != 'locked':
        poimanagerlogic.toggle_periodic_refocus(True)
        wait_for("refocus done", time_limit=20)


def stop_tracking():
    progress("Stopping tracking")
    poimanagerlogic.toggle_periodic_refocus(False)
    if optimizerlogic.module_state() == 'locked':
        wait_for('refocus done', time_limit=20)


def set_laser_power(power):
    aomlogic.set_power(power * 1e-3)


def mw_on():
    progress("Microwaves on")
    pulsedmeasurementlogic.microwave().cw_on()


def mw_off():
    progress("Microwaves off")
    pulsedmeasurementlogic.microwave().off()

def set_mw(frequency, power):
    progress("Setting microwaves to {} MHz at {} dBm".format(frequency*1e-6, power))
    mw_off()
    pulsedmasterlogic.set_ext_microwave_settings({'frequency': frequency, 'power': power})

def setup_pulsed(poi, sequence, tau_start, tau_step, points, rabi_period=0):
    params = {'tau_start': tau_start * 1e-9,
              'tau_step': tau_step * 1e-9,
              'number_of_taus': points,
              'mw_channel': 'd_ch3',
              'laser_length': 3 * 1e-6,
              'channel_amp': 0.0,
              'delay_length': 1e-6,
              'wait_time': 1.5e-6,
              'rabi_period': rabi_period * 1e-9,
              'sync_trig_channel': 'd_ch7',
              'gate_count_channel': 'd_ch8'}

    progress('Loading pulse ensemble {} for {}'.format(sequence, poi))
    progress('Rabi period: {} step: {} ns points: {}'.format(rabi_period, tau_step, points))
    pulsedmasterlogic.generate_predefined_sequence(sequence, kwarg_dict=params)
    wait_for('predefined generated', check_period=1, time_limit=10)
    pulsedmasterlogic.sample_ensemble(sequence, True)
    wait_for('asset loaded', check_period=1, time_limit=10)
    time.sleep(1)
    progress('Loaded pulse ensemble {} for {}'.format(sequence, poi))


def start_pulsed():
    if optimizerlogic.module_state() == 'locked':
        wait_for('refocus done')
    # Check for optimizer running or just always turn on just before?
    # Will go wrong if the pulsed measurement is started after the optimizer
    # so the safe bet is to turn it on just before and wait for it to complete the first
    progress('Starting pulsed measurement')
    clear_flag('measurement status updated')
    pulsedmasterlogic.toggle_pulsed_measurement(True)
    wait_for('measurement status updated', check_period=1, time_limit=6)
    time.sleep(1)

def stop_pulsed():
    progress('Stopping pulsed measurement')
    clear_flag('measurement status updated')
    pulsedmasterlogic.manually_pull_data()
    pulsedmasterlogic.toggle_pulsed_measurement(False)
    wait_for('measurement status updated', check_period=1, time_limit=6)
    time.sleep(1)


def setup_rabi(poi, tau_start=10, tau_step=10, points=80):
    setup_pulsed(poi, 'rabi', tau_start, tau_step, points)


def fit_rabi(poi):
    clear_flag('pulsed fit updated')
    pulsedmasterlogic.do_fit('rabi')  # using the name in the drop down
    wait_for('pulsed fit updated', check_period=1, time_limit=30)
    if pulsedmeasurementlogic.fc.current_fit_result is not None:
        fitparams = extract_fit_parameters('rabi', pulsedmeasurementlogic.fc.current_fit_result.params)
        rabi_frequency = fitparams['rabi_frequency']
        rabi_period = 1e9 / rabi_frequency
        progress("Fitted rabi period {} ns".format(rabi_period))
        fitparams.update({'rabi_period': rabi_period})
        update_poi_record(poi, fitparams)
        return True
    else:
        progress('fit failed')
        return False

def setup_ramsey(poi, tau_start=10, tau_step=10, points=100):
    rabi_period = acc[poi]['rabi_period']
    setup_pulsed(poi, 'ramsey', tau_start, tau_step, points, rabi_period)

def setup_hahn(poi, tau_start=10, tau_step=10, points=40):
    rabi_period = acc[poi]['rabi_period']
    setup_pulsed(poi, 'hahn_echo', tau_start, tau_step, points, rabi_period)

def pulsed_elapsed_time():
    return pulsedmeasurementlogic.elapsed_time()

def save_pulsed(poi, experiment):
    progress('Saving data for {} {}'.format(poi, experiment))
    pulsedmeasurementlogic.save_measurement_data(experiment)
    time.sleep(5)

def doze(duration):
    elapsed = 0
    progress("Waiting for {} m".format(int(duration/60)))
    while elapsed < duration:
        if duration - elapsed < 60:
            time.sleep(duration - elapsed)
        else:
            time.sleep(60)
            progress("{} m remaining".format(int((duration-elapsed)/60)))
            if not check_ok_to_go():
                progress('Told to stop, raising exception to stop now')
                raise
            elapsed += 60
    progress("Waking up")
