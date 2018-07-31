import datetime
from collections import OrderedDict
import logic.optimizerlogic

def save_optimizer():

    image_data = optimizerlogic.xy_refocus_image[:, :, 3]

    filepath = workstacklogic._save_logic.get_path_for_module('Confocal')
    timestamp = datetime.datetime.now()
    parameters = OrderedDict()

    parameters['XY image range (m)'] = optimizerlogic.refocus_XY_size
    parameters['XY resolution (samples per range)'] = optimizerlogic.optimizer_XY_res
    parameters['Z image range (m)'] = optimizerlogic.refocus_Z_size
    parameters['Z resolution (samples per range)'] = optimizerlogic.optimizer_Z_res

    image_data = OrderedDict()
    image_data['Optimiser Confocal pure XY scan image data without axis.\n'
        'The upper left entry represents the signal at the upper left pixel position.\n'
        'A pixel-line in the image corresponds to a row '
        'of entries where the Signal is in counts/s:'] = optimizerlogic.xy_image[:, :, 3]
    filelabel = 'opt_xy_image'
    workstacklogic.savelogic.save_data(image_data,
                               filepath=filepath,
                               timestamp=timestamp,
                               parameters=parameters,
                               filelabel=filelabel,
                               fmt='%.6e',
                               delimiter='\t')
    filelabel = 'opt_z'
    workstacklogic.savelogic.save_data(optimizerlogic.z_refocus_line,
                               filepath=filepath,
                               timestamp=timestamp,
                               parameters=parameters,
                               filelabel=filelabel,
                               fmt='%.6e',
                               delimiter='\t')


