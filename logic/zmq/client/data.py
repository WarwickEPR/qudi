import logging
from .QudiControl import QudiClient
from .. common import TablesContext


class FilepathNotSet(Exception):
    pass


class DataStorage(QudiClient):

    name = "data"
    log = logging.getLogger('client.data')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._local_filepath = None

    # sets the name of the archive where data will be stored
    # returns the name in use
    async def open_session(self, name=None, title=''):
        return await self.query('open_session', body={'name': name, 'title': title})

    # sets the archive name back to an anonymous timestamped location
    async def close_session(self, name=None, title=''):
        await self.send_command('open_session', body={'name': name, 'title': title})

    async def get_session_name(self):
        return await self.query('get_session_name')

    async def update_filepath(self):
        self._local_filepath = await self.query('local_filepath')

    async def local_filepath(self):
        if not self._local_filepath:
            self._local_filepath = await self.query('local_filepath')
        return self._local_filepath

    @property
    def filepath(self):
        if self._local_filepath:
            return self._local_filepath
        else:
            raise FilepathNotSet

    async def shared_filepath(self):
        await self.query('shared_filepath')

    def tables_context(self):
        return TablesContext(self.filepath, logger=self.log)
