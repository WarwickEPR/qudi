from tables import *
from . tables_context import TablesContext
from . timestamp import get_timestamp

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

    root = '/pulsed'

    def __init__(self, measurement=None, tc=None):
        if measurement is not None:
            # path to measurement group
            self._measurement = measurement
        self._tables_context = tc

    # Initialise a new measurement
    @classmethod
    def new_measurement(cls, tc: TablesContext, name=None, predefined_params={}):
        measurement_name = name + '_' + get_timestamp()
        with tc as th:
            g = th.tables.create_group(cls.root, measurement_name, createparents=True)
            for k, v in predefined_params.items():
                g._v_attrs['predefined_'+k] = v

            # link to POI

            return PulsedMeasurement(measurement=g._v_pathname, tc=tc)

    def update_array(self, data, attrs=None):
        with self._tables_context as th:
            group = th.get_node(self._measurement)
            measurement_group = self._path
        try:
            array = th.tables.get_node(self._measurement, classname='Array')
            array[...] = data
        except NoSuchNodeError:
            array = th.tables.create_array(self._measurement, data, createparents=True)
        if attrs is not None:
            for k, v in attrs.items():
                array._v_attrs[k] = v

    def _save_data(self, extracted=None, laser=None, raw=None, attrs=None):
        with self._tables_context as th:
            if extracted is not None:
                try:
                    table = th.tables.get_node(self._path, name='extracted', classname='Table')
                    table[:] = list(extracted)
                except NoSuchNodeError:
                    table = th.tables.create_table(self._path, name='extracted', createparents=True)
                    table.append(list(extracted))
            if laser is not None:
                self._update_array(th, 'laser', laser, attrs=attrs)
            if raw is not None:
                self._update_array(th, 'raw', raw, attrs=attrs)

    def take_snapshot(self):
        with self._tables_context as th:
            measurement_group = self._path
            # copy arrays to snapshot dir
            t = timestamp()
            for node in ['extracted', 'laser', 'raw']:
                th.tables.copy_node('/'.join([measurement_group, node]),
                                    '/'.join([measurement_group, 'snapshot', t, node]),
                                    createparents=True)

    @classmethod
    def list_measurements(cls, tc, prefix=None, poi=None):
        with tc as th:
            if poi is None:
                measurements = th.tables.list_nodes('/pulsed')
            else:
                measurements = th.tables.list_nodes('/'.join(['/site', poi, 'pulsed']))
            if prefix is not None:
                measurements = [filter(lambda x: x.startswith(prefix), measurements)]
            return measurements

    def list_snapshots(self):
        with self._tables_context as th:
            return th.tables.list_nodes('/'.join([self._measurement, 'snapshots']))

    def _get(self, thing, snapshot=None):
        with self._tables_context as th:
            if snapshot is not None:
                path = '/'.join(['/pulsed', self._path, 'snapshot', snapshot, thing])
            else:
                path = '/'.join(['/pulsed', self._path, thing])
            return th.tables.get_node(path, 'Array')

    def get_extracted(self, snapshot=None):
        return self._get('extracted', snapshot=snapshot)

    def get_laser(self, snapshot=None):
        return self._get('laser', snapshot=snapshot)

    def get_raw(self, snapshot=None):
        return self._get('raw', snapshot=snapshot)
