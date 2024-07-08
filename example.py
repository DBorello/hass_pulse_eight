#ssh -fN -R 10.0.50.166:50005:192.168.10.22:50005 vmuser@76.141.9.233

import logging
import asyncio

from pyp8 import async_get_amp_controller

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

host = '10.0.50.166'
port = 50005

async def cb(message):
    LOG.debug(f'CB: {message}')

async def main():
    amp =  await async_get_amp_controller(host, port, status_cb=cb)
    await amp.connect()

    await amp.get_status(4)

    # await amp.set_volume(4,2)
    # await amp.set_mute(4,0)
    await asyncio.sleep(10)  
    #await amp.connection.close()
    
asyncio.run(main())