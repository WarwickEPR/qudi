from .QudiControl import QudiClient
import h5py


class DataStore(QudiClient):

    name = "datastore"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    async def session(self):
        await self.send_command('get_session')
        reply = await self.receive_message()
        return reply.body

    @session.setter
    async def session(self, session_name):
        await self.send_command('set_session', body=session_name)

    async def filepath(self):
        await self.send_command('path')
        reply = await self.receive_message()
        return reply.body

    @staticmethod
    def hdf(filepath):
        return h5py.File(filepath, 'r', swmr=True)

    async def active_hdf(self, x):
        path = await self.filepath()
        return self.hdf(path)


def list_sites(hdf):
    return list(hdf['/sites'].keys())


def list_measurement_tree(hdf):
    measurement_list = []

    def record(x):
        if not x.starts_with('/site'):
            measurement_list.append(x)

    hdf.visit(record)
    return measurement_list

