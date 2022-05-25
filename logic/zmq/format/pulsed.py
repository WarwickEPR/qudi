from tables import *
from .. common import TablesHandle, TablesContext

# a group with raw data and current extraction
# Pulsed/my_measurement_starttime (+attrs) <group>
# Pulsed/my_measurement_starttime/extracted (+attrs) <array>
# Pulsed/my_measurement_starttime/laser (+attrs) <array>
# Pulsed/my_measurement_starttime/raw (+attrs) <array>
# Pulsed/my_measurement_starttime/snapshot/<time>/extracted,laser,raw


class ExtractedPulsedMeasurementTable(IsDescription):
    variable = Float32Col(pos=0)
    signal = Float32Col(pos=1)
    signal_err = Float32Col(pos=2)
    signal_alt = Float32Col(pos=3)
    signal_alt_err = Float32Col(pos=4)


class PulsedMeasurement:

    def __init__(self, measurement_group):
        self._path = measurement_group

    @classmethod
    def create_group(cls, h: TablesHandle, name, predefined_params={}):
        g = h.create_group('/pulsed', name)
        # add attrs
        g.attrs.update(predefined_params)

        return PulsedMeasurement(g._v_path)

    def _update_array(self, h: TablesHandle, node, data, attrs=None):
        measurement_group = self._path
        try:
            array = h.tables.get_node(measurement_group, name=node, classname='Array')
            array[...] = data
        except NoSuchNodeError:
            array = h.tables.create_array(measurement_group, node, data, createparents=True)
        if attrs is not None:
            array.attrs.update(attrs)

    def _save_data(self, h: TablesHandle, extracted=None, laser=None, raw=None, attrs=None):
        if extracted is not None:
            try:
                table = h.tables.get_node(self._path, name='extracted', classname='Table')
                table[:] = list(extracted)
            except NoSuchNodeError:
                table = h.tables.create_table(self._path, name='extracted', createparents=True)
                table.append(list(extracted))
        if laser is not None:
            self._update_array(h, 'laser', laser, attrs=attrs)
        if raw is not None:
            self._update_array(h, 'raw', raw, attrs=attrs)

    def take_snapshot(self, h: TablesHandle):
        measurement_group = self._path
        # copy arrays to snapshot dir
        timestamp = TablesContext.timestamp()
        for node in ['extracted', 'laser', 'raw']:
            h.tables.copy_node('/'.join([measurement_group, node]),
                               '/'.join([measurement_group, 'snapshot', timestamp, node]),
                               createparents=True)

    @classmethod
    def list_measurements(cls, h: TablesHandle, prefix=None, poi=None):
        if poi is None:
            measurements = h.tables.list_nodes('/pulsed')
        else:
            measurements = h.tables.list_nodes('/'.join(['/site', poi, 'pulsed']))
        if prefix is not None:
            measurements = [filter(lambda x: x.startswith(prefix), measurements)]
        return measurements

    def list_snapshots(self, h: TablesHandle):
        return h.tables.list_nodes('/'.join([self._path, 'snapshots']))

    def _get(self, h: TablesHandle, thing, snapshot=None):
        if snapshot is not None:
            path = '/'.join(['/pulsed', self._path, 'snapshot', snapshot, thing])
        else:
            path = '/'.join(['/pulsed', self._path, thing])
        return h.tables.get_node(path, 'Array')

    def get_extracted(self, h: TablesHandle, snapshot=None):
        return self._get(h, 'extracted', snapshot=snapshot)

    def get_laser(self, h: TablesHandle, snapshot=None):
        return self._get(h, 'laser', snapshot=snapshot)

    def get_raw(self, h: TablesHandle, snapshot=None):
        return self._get(h, 'raw', snapshot=snapshot)
