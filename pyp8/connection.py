import asyncio
import socket
import logging

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class AsyncSocketConnection:
    def __init__(self, host, port, response_cb, reconnect_delay=10):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.callback = response_cb
        self.reconnect_delay = reconnect_delay
        LOG.debug('Starting AsyncSocketConnection')

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            LOG.debug(f"Connected to {self.host}:{self.port}")
            asyncio.create_task(self.read_loop())
        except Exception as e:
            LOG.error(f"Connection failed: {e}")
            await self.reconnect()

    async def read_loop(self):
        while True:
            try:
                data = await self.reader.read(1024)
                if data:
                    for d in data.decode().split('\r\n'):
                        if d != '':
                            LOG.debug(f"Received: {d}")
                            await self.callback(d)
                else:
                    LOG.debug("Connection closed by server.")
                    await self.reconnect()
                    break
            except Exception as e:
                LOG.error(f"Read loop error: {e}")
                await self.reconnect()
                break

    async def send_command(self, command):
        LOG.debug(f'Sending: {command}')
        self.writer.write(command.encode())
        await self.writer.drain()

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            LOG.debug("Connection closed.")

    async def reconnect(self):
        LOG.debug(f"Attempting to reconnect in {self.reconnect_delay} seconds...")
        await asyncio.sleep(self.reconnect_delay)
        await self.connect()
