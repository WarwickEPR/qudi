
import time

poi_keys = poimanagerlogic.get_all_pois()
poi_keys = poi_keys[1:-1]
poi_names = [poimanagerlogic.poi_list[x]._name for x in poi_keys]


guide = 'A'

coarse_xy_range = 3e-6
coarse_xy_resolution = 20
coarse_z_range = 2e-6
coarse_z_resolution = 15
coarse_clock = 40

fine_xy_range = 1200e-9
fine_xy_resolution = 20
fine_z_range = 1500e-9
fine_z_resolution = 15
fine_clock = 20

def optimise_coarse(poikey=None):
    optimizerlogic.set_refocus_XY_size(coarse_xy_range)
    optimizerlogic.set_refocus_Z_size(coarse_z_range)
    optimizerlogic.optimizer_XY_res = coarse_xy_resolution
    optimizerlogic.optimizer_Z_res = coarse_z_resolution
    optimizerlogic.set_clock_frequency(coarse_clock)
    if poikey is None:
        p = None
    else:
        p = poimanagerlogic.get_poi_position(poikey=poikey)
    optimizerlogic.start_refocus(initial_pos=p)

def reset_optimise():
    optimizerlogic.set_refocus_XY_size(fine_xy_range)
    optimizerlogic.set_refocus_Z_size(fine_z_range)
    optimizerlogic.optimizer_XY_res = fine_xy_resolution
    optimizerlogic.optimizer_Z_res = fine_z_resolution
    optimizerlogic.set_clock_frequency(fine_clock)

def optimise_fine(poikey=None):
    optimizerlogic.set_refocus_XY_size(fine_xy_range)
    optimizerlogic.set_refocus_Z_size(fine_z_range)
    optimizerlogic.optimizer_XY_res = fine_xy_resolution
    optimizerlogic.optimizer_Z_res = fine_z_resolution
    optimizerlogic.set_clock_frequency(fine_clock)
    if poikey is None:
        p = None
    else:
        p = poimanagerlogic.get_poi_position(poikey=poikey)
    optimizerlogic.start_refocus(initial_pos=p)

def optimise_fine_n(poi):
    poikey = lookup_poi(poi)
    optimise_fine(poikey)

def update_sample_position(poikey):
    position = scannerlogic.get_position()
    poimanagerlogic.set_new_position(poikey, position)

def update_sample_position_n(poi):
    poikey = lookup_poi(poi)
    update_sample_position(poikey)


def update_point_position(poikey):
    position = scannerlogic.get_position()
    poimanagerlogic.move_coords(poikey, position)
    poimanagerlogic.save_poi_map_as_roi()

def record_position_history():
    position = scannerlogic.get_position()
    target = workstacklogic.current_target()
    sample = poimanagerlogic.get_poi_position('sample')
    with open('c:/Users/Confocal/phistory.dat','a') as f:
        f.write("{} {} {} {} {} {} {} {}\n".format(target,time.time(),position[0],position[1],position[2],sample[0],sample[1],sample[2]))
    #history = workstacklogic.fetch('phistory')
    #if history == 0.0:
    #    history = []
    #history.append((time.time(), target, position, sample))
    #workstacklogic.store('phistory',history)

def do_psat():
    aomlogic.run_psat()


#guide = 'poi_20180212_2214_54_725750'
#guidename = 'poi_221454'

a = [('track guide {}', optimise_fine, [guide]),
     'wait',
     ('update sample', update_sample_position, [guide]),
     ('coarse focus {}', optimise_coarse, ['_X_']),
     'wait',
     ('fine focus', optimise_fine, []),
     'wait',
     ('correct position', update_point_position, ['_X_']),
     aomlogic.run_psat,
     aomlogic.save_psat,
     hbtlogic.start_hbt,
     ('HBT timer', 'timer', [10]),
     'wait',
     hbtlogic.stop_hbt,
     hbtlogic.save_hbt,
     ('done', 'log', ['_X_'])]

def reset_laser():
    aomlogic.set_power(0.02)

def do_psat():
    aomlogic.run_psat()
    aomlogic.save_psat()
    psat = aomlogic.fitted_Psat
    if psat > 0.003:
        power = 0.003
    elif psat < 0.0008:
        power = 0.0015
    else:
        power = psat
    aomlogic.set_power(power)
    workstacklogic.store('Psat', aomlogic.fitted_Psat)
    workstacklogic.store('Isat', aomlogic.fitted_Isat)
    workstacklogic.store('power', power)

def stop_hbt():
    hbtlogic.stop_hbt()
    hbtlogic.save_hbt()
    workstacklogic.store('g2min', min(hbtlogic.g2_data_normalised))

def stop_odmr():
    odmrlogic.stop_odmr_scan()
    odmrlogic.do_fit()
    f = odmrlogic.fc.current_fit_result.best_values['center']
    s = odmrlogic.fc.current_fit_result.best_values['sigma']
    odmrlogic.save_odmr_data()
    workstacklogic.store('odmr_frequency', f)
    workstacklogic.store('odmr_width', 2*s)

def estimated_revival(f):
    return int(round(5.1492 * f/1e6 - 7448.3))

def load_rabi():
    odmr_frequency = workstacklogic.fetch('odmr_frequency')
    params = {'tau_start': 10.0e-9,
              'tau_step': 10.0e-9,
              'number_of_taus': 80,
              'mw_channel': 'd_ch3',
              'laser_length': 3.0e-6,
              'channel_amp': 0.0,
              'delay_length': 1e-6,
              'wait_time': 1.5e-6,
              'sync_trig_channel': 'd_ch7',
              'gate_count_channel': 'd_ch8'};
    pulsedmasterlogic.generate_predefined_sequence('rabi', params)
    pulsedmasterlogic.sample_block_ensemble('rabi', True)
    workstacklogic.store("finish_time", round(time.time())+90)

ramsey_tau_start = 40e-9
ramsey_tau_incr = 40e-9
ramsey_points = 200
ramsey_duration = 600

def load_ramsey():
    odmr_frequency = workstacklogic.fetch('odmr_frequency')
    rabi_period = int(round(workstacklogic.fetch('rabi_period')))
    workstacklogic.log.info("Ramsey with Rabi period {} ns".format(rabi_period))
    if rabi_period < 90 or rabi_period > 250:
        # duff fit/rabi
        move_on("Rabi doesn't seem right")
    else:
        workstacklogic.log.info("Rabi period: {} ns".format(rabi_period))
        params = {'tau_start': ramsey_tau_start,
                  'tau_incr': ramsey_tau_incr,
                  'num_of_points': ramsey_points,
                  'rabi_period': rabi_period * 1e-9,
                  'mw_channel': 'd_ch3',
                  'laser_length': 3.0e-6,
                  'channel_amp': 0.0,
                  'delay_length': 1e-6,
                  'wait_time': 1.5e-6,
                  'sync_trig_channel': 'd_ch7',
                  'gate_count_channel': 'd_ch8'};
        pulsedmasterlogic.generate_predefined_sequence('ramsey', params)
        pulsedmasterlogic.sample_block_ensemble('ramsey', True)
        workstacklogic.store("finish_time", round(time.time())+ramsey_duration)


echo_start_periods = 1
echo_incr_periods = 4
echo_points = 40
echo_duration = 6000

def load_hahn_echo():
    odmr_frequency = workstacklogic.fetch('odmr_frequency')
    period = estimated_revival(odmr_frequency) * 1e-9
    rabi_period = int(round(workstacklogic.fetch('rabi_period')))*1e-9
    workstacklogic.log.info("Echo decay tau_start={} us tau_incr={} us points={} time={} us".format(period*echo_start_periods*1e6,
                                                                                                    period*echo_incr_periods*1e6,
                                                                                                    echo_points,
                                                                                                    period*echo_start_periods+period*echo_incr_periods*echo_points*1e6))
    params = {'tau_start': period*echo_start_periods,
              'tau_incr': period*echo_incr_periods,
              'num_of_points': echo_points,
              'rabi_period': rabi_period,
              'mw_channel': 'd_ch3',
              'laser_length': 3.0e-6,
              'channel_amp': 0.0,
              'delay_length': 1e-6,
              'wait_time': 1.5e-6,
              'sync_trig_channel': 'd_ch7',
              'gate_count_channel': 'd_ch8'};
    pulsedmasterlogic.generate_predefined_sequence('hahnecho', params)
    pulsedmasterlogic.sample_block_ensemble('hahn_echo', True)
    workstacklogic.store("finish_time", (round(time.time())) + echo_duration)

def lookup_poi(poi):
    logging("Lookup up POI {}".format(poi))
    poikey = poimanagerlogic.poi_lookup[poi]
    logging("Found POI key {}".format(poikey))
    return poikey

def logging(msg):
    workstacklogic.log.info(msg)


def move_on(msg):
    workstacklogic.insert_actions([('Failed step {}', 'log', [msg]), ('pause', 'timer', [2]), 'wait', 'next target'])

def finish_rabi():
    pulsedmeasurementlogic.do_fit('Sin')
    values = pulsedmeasurementlogic.fc.current_fit_result.best_values
    rabi_period = 1e9/values['frequency'] # ns
    amplitude = values['amplitude']
    workstacklogic.log.info("{} Rabi: {} Amplitude: {} chisqr: {}".format(workstacklogic.current_target(), rabi_period, amplitude, pulsedmeasurementlogic.fc.current_fit_result.chisqr))
    workstacklogic.store('rabi_period', rabi_period)
    workstacklogic.store('rabi_amplitude', amplitude)
    workstacklogic.store('rabi_chisqr', pulsedmeasurementlogic.fc.current_fit_result.chisqr)
    t = workstacklogic.current_target()
    pulsedmeasurementlogic.save_measurement_data(tag=t+'_Rabi')
    if rabi_period < 90 or rabi_period > 250 or amplitude < 0.03:
        # duff fit/rabi
        move_on("Rabi doesn't seem right")

def finish_echo():
    pulsedmeasurementlogic.do_fit('Stretched exponential')
    values = pulsedmeasurementlogic.fc.current_fit_result.best_values
    workstacklogic.store('echo_decay_n', values['beta'])
    workstacklogic.store('echo_decay_lifetime', values['lifetime'])
    t = workstacklogic.current_target()
    pulsedmeasurementlogic.save_measurement_data(tag=t+'_EchoDecay')

def finish_ramsey():
    pulsedmeasurementlogic.do_fit('Sin')
    values = pulsedmeasurementlogic.fc.current_fit_result.best_values
    workstacklogic.store('ramsey_frequency', values['frequency'])
    workstacklogic.store('ramsey_lifetime', values['lifetime'])
    t = workstacklogic.current_target()
    pulsedmeasurementlogic.save_measurement_data(tag=t+'+Ramsey')

def setup_pulsed():
    odmr_frequency = workstacklogic.fetch('odmr_frequency')
    if odmr_frequency < 2.15e9 or odmr_frequency > 2.17e9:
        move_on("ODMR frequency not right")
    pulsedmeasurementlogic.set_microwave_params(frequency=odmr_frequency)

def start_tracking(poikey=None):
    if poikey is None:
        poikey = workstacklogic.current_target()
    poimanagerlogic.start_periodic_refocus(poikey)

def stop_tracking():
    poimanagerlogic.stop_periodic_refocus()
    poimanagerlogic.timer.stop() # doesn't always stop

def start_pulsed():
    if optimizerlogic.module_state() == 'locked':
        workstacklogic.insert_actions(['wait refocus', ('pause', 'timer', [30]), 'wait timer', start_pulsed])
    else:
        pulsedmasterlogic.start_measurement()

def stop_pulsed():
    if optimizerlogic.module_state() == 'locked':
        workstacklogic.insert_actions(['wait refocus', ('pause', 'timer', [40]), 'wait timer', stop_pulsed])
    else:
        pulsedmasterlogic.stop_measurement()

def update_sample_if_good():
    t = workstacklogic.current_target()
    if counterlogic.countdata[0][0] > 15000:
        update_point_position(t)

def check_count_rate():
    rate = counterlogic.countdata[0][0]
    if rate < 30000:
        # hasn't found anything
        move_on('Count rate unusually low: {}'.format(rate))

refocusing_period = 210
def refocus_period():
    finish_time = workstacklogic.fetch("finish_time")
    if finish_time - time.time() < refocusing_period:
        t = round(finish_time - time.time()) + 30
    else:
        t = refocusing_period
    pause_and_refocus = [
        ('wait a refocus period', 'timer', [t]), 'wait timer',
        pulsedmasterlogic.pause_measurement,
        optimise_fine,
        'wait refocus',
        update_sample_if_good,
        pulsedmasterlogic.continue_measurement,
        refocus_period
    ]
    if time.time() < finish_time:
        workstacklogic.insert_actions(pause_and_refocus)

def dummy_test():
    p = workstacklogic.current_target()
    if p.endswith('8'):
        workstacklogic.insert_actions([('Found an 8', 'log', [p]), ('pause', 'timer', [2]), 'wait', 'next target'])

test_decision = [#('Testing {}','log',['_X_']),
                 dummy_test,
                 #('Passed {}', 'log', ['_X_']),
                 ('pause', 'timer', [2]), 'wait'
                 ]

#guide = poi_keys[3]
#random.shuffle(poi_keys)
roi_update_wait = 10

a = [('track guide {}', optimise_fine, [guide]), 'wait',
     ('pause', 'timer', [5]), 'wait',
     ('update sample', update_sample_position, [guide]),
     ('pause', 'timer', [roi_update_wait]), 'wait',
     ('coarse focus {}', optimise_coarse, ['_X_']), 'wait',
     ('pause', 'timer', [5]), 'wait',
     ('fine focus', optimise_fine, []), 'wait',
     ('pause', 'timer', [3]), 'wait',
     ('correct position', update_point_position, ['_X_']),
     ('pause', 'timer', [3]), 'wait',
     do_psat,
     hbtlogic.start_hbt,
     ('HBT timer', 'timer', [90]),
     'wait',
     stop_hbt,
#     ('pause', 'timer', [5]), 'wait',
#     odmrlogic.start_odmr_scan,
#     ('ODMR timer', 'timer', [30]),
#     'wait',
#     stop_odmr,
     ('pause', 'timer', [2]), 'wait',
     workstacklogic.save,
     ('done', 'log', ['_X_'])]

d = [
     ('coarse focus {}', optimise_coarse, ['_X_']), 'wait',
     ('pause', 'timer', [5]), 'wait',
     do_psat,
     hbtlogic.start_hbt,
     ('HBT timer', 'timer', [90]),
     'wait',
     stop_hbt,
     ('pause', 'timer', [5]), 'wait',
     workstacklogic.save,
     ('done', 'log', ['_X_'])]

#rabi_time = 60
#ramsey_time = 60
#echo_time = 60

b = [ setup_pulsed,
     ('track guide {}', optimise_fine, [guide]), 'wait refocus',
     ('pause', 'timer', [5]), 'wait timer',
     ('update sample', update_sample_position, [guide]),
     ('attempt focus {}', optimise_fine, ['_X_']), 'wait refocus',
     ('pause', 'timer', [10]), 'wait timer',
     reset_optimise,
     check_count_rate,
     load_rabi, 'wait pulse upload',
     ('pause', 'timer', [10]), 'wait timer',
     start_pulsed,
     refocus_period,
     stop_pulsed,
     ('pause', 'timer', [5]), 'wait timer',
     finish_rabi,
     ('pause', 'timer', [5]), 'wait timer',
     load_ramsey, 'wait pulse upload',
     ('pause', 'timer', [10]), 'wait timer',
     start_pulsed,
     refocus_period,
     stop_pulsed,
     ('pause', 'timer', [5]), 'wait timer',
     finish_ramsey,
     ('pause', 'timer', [5]), 'wait timer',
     load_hahn_echo, 'wait pulse upload',
     ('pause', 'timer', [10]), 'wait timer',
     start_pulsed,
     refocus_period,
     stop_pulsed,
     ('pause', 'timer', [5]), 'wait timer',
     finish_echo,
     ('pause', 'timer', [5]), 'wait timer',
     workstacklogic.save,
     ('pause', 'timer', [5]), 'wait timer',
     ('done', 'log', ['_X_'])]


def loop_targets():
    if workstacklogic.target_index + 1 == len(workstacklogic.targets):
        workstacklogic.target_index = 0

guide = 'A'

check_refocus = [
    ('track guide {}', optimise_fine_n, [guide]), 'wait refocus',
    ('pause', 'timer', [5]), 'wait timer',
    ('update sample', update_sample_position_n, [guide]),
    ('attempt focus {}', optimise_fine_n, ['_X_']), 'wait refocus',
    ('pause', 'timer', [10]), 'wait timer',
    record_position_history,
    loop_targets
]

#old = 'z:/Sample Data/Confocal/2018/02/20180216/Workstack/20180216-1159-06_workstack.dat'
#workstacklogic.save_values = ['Psat', 'Isat', 'power', 'g2min', 'odmr_frequency', 'odmr_width']
#workstacklogic.load_store_from_file(old)

workstacklogic.save_values = ['Psat', 'Isat', 'power', 'g2min', 'odmr_frequency', 'odmr_width',
                              'rabi_period', 'rabi_amplitude','rabi_chisqr',
                              'echo_decay_n', 'echo_decay_lifetime', 'ramsey_frequency', 'ramsey_lifetime']
workstacklogic.save_values = ['Psat', 'Isat', 'power', 'g2min', 'odmr_frequency', 'odmr_width']
workstacklogic.actions = a
workstacklogic.targets=poi_keys

#workstacklogic.actions = check_refocus
#workstacklogic.targets= ['poi_20180212_2242_55_546701', 'poi_20180212_2146_33_052320']
