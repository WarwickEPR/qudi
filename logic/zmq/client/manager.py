import logging
from .QudiControl import QudiClient
from .. data.tables_context import TablesContext
import os
import asyncio


class FilepathNotSet(Exception):
    pass


class Manager(QudiClient):

    name = "manager"
    log = logging.getLogger('client.general')

    def __init__(self, *args, **kwargs):
        super(Manager, self).__init__(*args, **kwargs)
        self._file_path = None
        self._tables_context = None

    # sets the archive where data will be stored
    # returns the path to the file
    # supply path relative to current directory
    async def attach_data_file(self, file=None, title=''):
        file_path = os.path.abspath(file)
        self._file_path = await self.query('attach_data_file', body={'file': file_path, 'title': title})
        self._tables_context = TablesContext(self._file_path, logger=self.log)

    async def detach_data_file(self):
        await self.send_command('detach_data_file')
        self._tables_context = None
        self._file_path = None

    async def storage_attached(self):
        return await self.query('storage_attached')

    async def storage_file_path(self):
        return await self.query('storage_file_path')

    @property
    def file_path(self):
        if self._file_path:
            return self._file_path
        else:
            raise FilepathNotSet

    @property
    def tables_context(self):
        return self._tables_context

    async def start_logic_module(self, module):
        await self.send_command('start_logic_module', module)

    async def start_logic_modules_bg(self, modules: list):
        start_commands = map(self.start_logic_module, modules)
        await asyncio.gather(*start_commands)

    async def start_logic_modules(self, modules: list):
        logic_modules_loaded = self.subscribe('manager.logic_modules_loaded')
        start_commands = map(self.start_logic_module, modules)
        await asyncio.gather(*start_commands)
        while True:
            status = await logic_modules_loaded.receive()
            if status:
                self.log.info("All modules loaded")
                break
