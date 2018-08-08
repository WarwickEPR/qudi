import random

guide = 'H15-21'


coarse_xy_range = 3.5e-6
coarse_xy_resolution = 23
coarse_z_range = 2e-6
coarse_z_resolution = 15
coarse_clock = 40

fine_xy_range = 1500e-9
fine_xy_resolution = 17
fine_z_range = 1500e-9
fine_z_resolution = 15
fine_clock = 20

def logging(msg):
    workstacklogic.log.info(msg)

def lookup_poi(poi):
    logging("Lookup up POI {}".format(poi))
    poikey = poimanagerlogic.poi_lookup[poi]
    logging("Found POI key {}".format(poikey))
    return poikey

def optimise_fine_n(poi):
    poikey = lookup_poi(poi)
    optimise_fine(poikey)

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
        poimanagerlogic.set_active_poi(poikey=poikey)

    optimizerlogic.start_refocus(initial_pos=p)

def optimise_coarse_n(poi):
    poikey = lookup_poi(poi)
    optimise_coarse(poikey)

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
        poimanagerlogic.set_active_poi(poikey=poikey)
    optimizerlogic.start_refocus(initial_pos=p)


def update_sample_position(poi):
    poikey = lookup_poi(poi)
    position = scannerlogic.get_position()
    poimanagerlogic.set_new_position(poikey, position)

def update_point_position(poikey):
    position = scannerlogic.get_position()
    poimanagerlogic.move_coords(poikey, position)
    poimanagerlogic.save_poi_map_as_roi()

def update_point_position_n(poi):
    poikey = lookup_poi(poi)
    update_point_position(poikey)

def update_active_poi(poi):
    poikey = lookup_poi(poi)
    poimanagerlogic.set_active_poi(poikey)

def do_psat():
    aomlogic.run_psat()
    aomlogic.save_psat()

def stop_hbt():
    hbtlogic.stop_hbt()
    hbtlogic.save_hbt()
    workstacklogic.store('g2min', min(hbtlogic.g2_data_normalised))

def check_counts():
    poi = workstacklogic.current_target()
    cr = counterlogic.countdata[0][0]
    workstacklogic.info("Count rate {} {}".format(poi,cr))
    if cr < 30e3:
        # unlikely to succeed
        workstacklogic.stack[workstacklogic.sp+1:] =\
            [('Count rate too low, skipping','log',['_X_']),
             ('pause', 'timer', [2]), 'wait',
            workstacklogic.save,
            ('pause', 'timer', [2]), 'wait',
            ('Saved, moving on', 'log', ['_X_'])]

roi_update_wait = 10

focus = [('track guide {}', optimise_coarse_n, [guide]), 'wait',
         ('pause', 'timer', [5]), 'wait',
         ('update sample', update_sample_position, [guide]),
         ('pause', 'timer', [roi_update_wait]), 'wait',
         ('coarse focus {}', optimise_coarse_n, ['_X_']), 'wait',
         ('pause', 'timer', [4]), 'wait',
         ('correct position', update_point_position_n, ['_X_']),
         ('pause', 'timer', [3]), 'wait',
         ('done', 'log', ['_X_'])]

hbt_work = [('track guide {}', optimise_fine_n, [guide]), 'wait',
       ('pause', 'timer', [5]), 'wait',
       ('update sample', update_sample_position, [guide]),
       ('pause', 'timer', [roi_update_wait]), 'wait',
       ('coarse focus {}', optimise_coarse_n, ['_X_']), 'wait',
       ('pause', 'timer', [5]), 'wait',
       ('fine focus', optimise_fine, []), 'wait',
       ('pause', 'timer', [3]), 'wait',
       ('correct position', update_point_position_n, ['_X_']),
       ('pause', 'timer', [3]), 'wait',
       ('update active poi {}', update_active_poi, ['_X_']),
       do_psat,
       ('pause', 'timer', [2]), 'wait',
       save_optimizer,
       check_counts,
       hbtlogic.start_hbt,
       ('HBT timer', 'timer', [120]),
       'wait',
       stop_hbt,
       ('pause', 'timer', [2]), 'wait',
       workstacklogic.save,
       ('done', 'log', ['_X_'])]

just_hbt = [
     ('coarse focus {}', optimise_coarse_n, ['_X_']), 'wait',
     ('pause', 'timer', [5]), 'wait',
     do_psat,
     hbtlogic.start_hbt,
     ('HBT timer', 'timer', [90]),
     'wait',
     stop_hbt,
     ('pause', 'timer', [5]), 'wait',
     workstacklogic.save,
     ('done', 'log', ['_X_'])]


poi_keys = poimanagerlogic.get_all_pois()
poi_keys = poi_keys[1:-1]
pois = [poimanagerlogic.poi_list[x]._name for x in poi_keys]
random.shuffle(pois)

#for i in ['M12-209','M12-248','M12-210','M12-236','M12-213','M12-218','M12-246']:
#    pois.remove(i)

workstacklogic.save_values = ['Psat', 'Isat', 'power', 'g2min']
workstacklogic.actions = hbt_work
workstacklogic.targets=pois