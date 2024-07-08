import logging
import re
from . import connection

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

ZONE_REGEXP = [ '\^\=PZ\.2 \@(?P<zone>\d+)\,(?P<power>[01])',    # Power status
                '\^\=VPZ\.2 \@(?P<zone>\d+)\,(?P<volume>\d+)',   # Volume status (0-100%)
                '\^\=MZ\.2 \@(?P<zone>\d+)\,(?P<mute>[01])',    # Mute status
                '\^\=SZ\.2 \@(?P<zone>\d+)\,(?P<source>\d+)' ] # Source status  

async def async_get_amp_controller(host, port, status_cb=None):

    class AmpControlAsync():
        def __init__(self, host, port):
            LOG.debug('Starting amp')
            self.host = host
            self.port = port
            self.status_cb = status_cb
            self.compile_regexp()

        def compile_regexp(self):
            self.regexp = []
            for r in ZONE_REGEXP:
                self.regexp.append(re.compile(r))

        async def connect(self):
            LOG.debug('Starting connection')
            self.connection = connection.AsyncSocketConnection(self.host, self.port, self.response_cb)
            await self.connection.connect()

        async def response_cb(self, message):
            #LOG.debug(f'CB: {message.strip()}')
            for regexp in self.regexp:
                match = regexp.match(message)
                if match:
                    #LOG.debug(f'Found response match: {match.groupdict()}')

                    # Convert power and mute to boolean
                    match_dict = match.groupdict()
                    for key in match_dict.keys():
                        if key == 'power' or key == 'mute':
                            match_dict[key] = bool(int(match_dict[key]))
                        else:
                            match_dict[key] = int(match_dict[key])

                    await self.status_cb(match_dict)
                    return
            
            #LOG.debug('No match found')
            #await self.status_cb({})

        async def get_status(self, zone):
            LOG.info(f'Getting status for zone {zone}')
            await self.connection.send_command(f'^PZ @{zone}, ?$')
            await self.connection.send_command(f'^VPZ @{zone}, ?$')
            await self.connection.send_command(f'^MZ @{zone}, ?$')
            await self.connection.send_command(f'^SZ @{zone}, ?$')



        async def set_power(self, zone: int, power: bool):
            if power:
                LOG.info(f'Powering on zone {zone}')
                await self.connection.send_command(f'^PZ @{zone}, 1$')
            else:
                LOG.info(f'Powering off zone {zone}')
                await self.connection.send_command(f'^PZ @{zone}, 0$')

        async def set_mute(self, zone: int, mute: bool):
            if mute:
                LOG.info(f'Muting zone {zone}')
                await self.connection.send_command(f'^MZ @{zone}, 1$')
            else:
                LOG.info(f'Unmuting zone {zone}')
                await self.connection.send_command(f'^MZ @{zone}, 0$')

        async def set_volume(self, zone: int, volume: int):
            LOG.info(f'Setting volume to {volume} on zone {zone}')
            await self.connection.send_command(f'^VPZ @{zone}, {volume}$')

        async def volume_up(self, zone: int, steps: int = 2):
            LOG.info(f'Volume up on zone {zone}')
            await self.connection.send_command(f'^VPZ @{zone}, +{steps}$')

        async def volume_down(self, zone: int, steps: int = 2):
            LOG.info(f'Volume down on zone {zone}')
            await self.connection.send_command(f'^VPZ @{zone}, -{steps}$')

        async def set_source(self, zone: int, source: int):
            LOG.info(f'Setting source to {source} on zone {zone}')
            await self.connection.send_command(f'^SZ @{zone}, {source}$')

    return AmpControlAsync(host, port)

