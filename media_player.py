import logging
import asyncio

from .pyp8 import async_get_amp_controller

import voluptuous as vol
from ratelimit import limits
from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity, MediaPlayerEntityFeature
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITY_NAMESPACE,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)

from .const import (
    DOMAIN,
#    SERVICE_JOIN,
#    SERVICE_UNJOIN,
)

LOG = logging.getLogger(__name__)

CONF_SOURCES = 'sources'
CONF_ZONES = 'zones'
CONF_HOST = 'host'
MAX_ZONES = 32
MINUTES = 60
MAX_VOLUME = 100
VOL_INCREMENT = 2

SUPPORTED_ZONE_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=64))
SOURCE_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME, default='Unknown Source'): cv.string}
)
ZONE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=64))
ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default='Audio Zone'): cv.string,
    }
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default='ProAudio'): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=50005): cv.positive_int,
        vol.Required(CONF_ZONES): vol.Schema({ZONE_IDS: ZONE_SCHEMA}),
        vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
    }
)
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    namespace = config.get(CONF_ENTITY_NAMESPACE)
    amp_name = config.get(CONF_NAME)
    entities = []
    
    LOG.debug('Setting up ProAudio platform')

    async def status_cb(message):
        #LOG.debug(f"Callback in integration with message: {message}")
        zone = message.get('zone')
        if zone is not None:
            zone_id = zone
            LOG.debug(f'Updating zone {zone_id} status: {message}')
            if zone_id in Zones.keys():
                await Zones[zone_id].update_status(message)
                await HMP.update_status(message)
            else:
                LOG.warning(f'Unknown zone "{zone_id}" of type {type(zone_id)} in message: {message}')
            
    

    amp = await async_get_amp_controller(config[CONF_HOST], config[CONF_PORT], status_cb=status_cb)
    await amp.connect()

    sources = {
        source_id: extra[CONF_NAME] for source_id, extra in config[CONF_SOURCES].items()
    }

    Zones = {}
    for zone_id, extra in config[CONF_ZONES].items():
        ZMP = ZoneMediaPlayer(namespace, amp_name, amp, sources, zone_id, extra[CONF_NAME])
        Zones[zone_id] = ZMP
        entities.append(ZMP)

    HMP = HomeMediaPlayer(namespace, amp_name, amp, sources, Zones)
    entities.append(HMP)

    async_add_entities(entities, True)

    # Get status of each zone
    for zone in Zones.values():
        await zone.get_status()

class ZoneMediaPlayer(MediaPlayerEntity):
    """Representation of a matrix amplifier zone."""

    def __init__(self, namespace, amp_name, amp, sources, zone_id, zone_name):
        """Initialize new zone."""
        self._amp = amp
        self._amp_name = amp_name
        self._name = zone_name
        self._zone_id = zone_id

        # FIXME: since this should be a logical media player...why is it not good enough for the user
        # specified name to represent this?  Other than it could be changed...
        self._unique_id = f'{DOMAIN}_{amp_name}_zone_{zone_id}'.lower().replace(
            ' ', '_'
        )

        LOG.info(f'Creating {self.zone_info} media player')

        self._status = {}
        self._status_snapshot = None

        self._source = None
        self._source_id_to_name = sources  # [source_id]   -> source name
        self._source_name_to_id = {
            v: k for k, v in sources.items()
        }  # [source name] -> source_id

        # sort list of source names
        self._source_names = sorted(
            self._source_name_to_id.keys(), key=lambda v: self._source_name_to_id[v]
        )
        # TODO: Ideally the source order could be overridden in YAML config (e.g. TV should appear first on list).
        #       Optionally, we could just sort based on the zone number, and let the user physically wire in the
        #       order they want (doesn't work for pre-amp out channel 7/8 on some Xantech)

       
    async def update_status(self, status):
        #LOG.debug('Updating status')
        self._status.update(status)

        source_id = status.get('source')
        if source_id:
            source_name = self._source_id_to_name.get(source_id)
            if source_name:
                self._source = source_name
            else:
                LOG.warning(f'Unknown source ID {source_id} for {self.zone_info}')

        self.async_schedule_update_ha_state()

    async def async_update(self):
        pass

    @property
    def zone_info(self):
        return f'{self._amp_name} zone {self._zone_id} ({self._name})'

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the powered on state of the zone."""
        power = self._status.get('power')
        if power is not None and power is True:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume = self._status.get('volume')
        if volume is None:
            return None
        return volume / MAX_VOLUME

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        # FIXME: what about when volume == 0?
        mute = self._status.get('mute')
        if mute is None:
            mute = False
        return mute

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORTED_ZONE_FEATURES

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    async def async_select_source(self, source):
        """Set input source."""
        if source not in self._source_name_to_id:
            LOG.warning(
                f"Selected source '{source}' not valid for {self.zone_info}, ignoring! Sources: {self._source_name_to_id}"
            )
            return

        source_id = self._source_name_to_id[source]
        LOG.info(f'Switching {self.zone_info} to source {source_id} ({source})')
        await self._amp.set_source(self._zone_id, source_id)

    async def async_turn_on(self):
        """Turn the media player on."""
        LOG.debug(f'Turning ON {self.zone_info}')
        await self._amp.set_power(self._zone_id, True)

    async def async_turn_off(self):
        """Turn the media player off."""
        LOG.debug(f'Turning OFF {self.zone_info}')
        await self._amp.set_power(self._zone_id, False)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        LOG.debug(f'Setting mute={mute} for zone {self.zone_info}')
        await self._amp.set_mute(self._zone_id, mute)

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0—1.0"""
        amp_volume = int(volume * MAX_VOLUME)
        LOG.debug(
            f'Setting zone {self.zone_info} volume to {amp_volume} (HA volume {volume}'
        )
        await self._amp.set_volume(self._zone_id, amp_volume)

    async def async_volume_up(self):
        LOG.debug(f'Volume up for zone {self.zone_info}')
        await self._amp.volume_up(self._zone_id, VOL_INCREMENT)

    async def async_volume_down(self):
        LOG.debug(f'Volume down for zone {self.zone_info}')
        await self._amp.volume_down(self._zone_id, VOL_INCREMENT)

    async def get_status(self):
        LOG.debug(f'Getting status for zone {self.zone_info}')
        await self._amp.get_status(self._zone_id)

    @property
    def icon(self):
        if self.state == STATE_OFF:
            return 'mdi:speaker-off'
        return 'mdi:speaker'

class HomeMediaPlayer(MediaPlayerEntity):
    """ Controls all zones"""

    def __init__(self, namespace, name, amp, sources, zone_players):
        self._name = name
        self._amp = amp
        self._amp_name = name
        self._zones = zone_players
        self._zone_id = ',@'.join([str(z) for z in self._zones.keys()]) # Convert to string common separated
        LOG.debug(f'Zone list for all {self._zone_id}')
        self._status = {}
        self._status['power'] = True
        self._source = None

        self._source_id_to_name = sources  # [source_id]   -> source name
        self._source_name_to_id = {
            v: k for k, v in sources.items()
        }  # [source name] -> source_id

        # sort list of source names
        self._source_names = sorted(
            self._source_name_to_id.keys(), key=lambda v: self._source_name_to_id[v]
        )
        # TODO: Ideally the source order could be overridden in YAML config (e.g. TV should appear first on list).
        #       Optionally, we could just sort based on the zone number, and let the user physically wire in the
        #       order they want (doesn't work for pre-amp out channel 7/8 on some Xantech)

        self._unique_id = f'{DOMAIN}_{namespace}_{name}'.lower().replace(' ', '_')


    async def update_status(self, status):
        self.async_schedule_update_ha_state()

    @property
    def zone_info(self):
        return f'{self._amp_name} zone {self._zone_id} ({self._name})'

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the powered on state of the zone."""
        for z in self._zones:
            if self._zones[z].state == STATE_ON:
                return STATE_ON
        return STATE_OFF # If one zone is on, on.  If all are off, off.

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        sum = 0
        ii = 0
        for zone in self._zones:
            if self._zones[zone].state == STATE_ON:
                volume = self._zones[zone].volume_level
                if volume is not None:
                    sum += volume
                    ii += 1
        return (sum/ii) if ii > 0 else 0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        for z in self._zones:
            if self._zones[z].is_volume_muted == False:
                return False
        return True

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORTED_ZONE_FEATURES

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    async def async_select_source(self, source):
        """Set input source."""
        if source not in self._source_name_to_id:
            LOG.warning(
                f"Selected source '{source}' not valid for {self.zone_info}, ignoring! Sources: {self._source_name_to_id}"
            )
            return

        source_id = self._source_name_to_id[source]
        LOG.info(f'Switching {self.zone_info} to source {source_id} ({source})')
        await self._amp.set_source(self._zone_id, source_id)

    async def async_turn_on(self):
        """Turn the media player on."""
        LOG.debug(f'Turning ON {self.zone_info}')
        await self._amp.set_power(self._zone_id, True)

    async def async_turn_off(self):
        """Turn the media player off."""
        LOG.debug(f'Turning OFF {self.zone_info}')
        await self._amp.set_power(self._zone_id, False)

    async def async_mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        LOG.debug(f'Setting mute={mute} for zone {self.zone_info}')
        await self._amp.set_mute(self._zone_id, mute)

    async def async_set_volume_level(self, volume):
        """Set volume level, range 0—1.0"""
        amp_volume = int(volume * MAX_VOLUME)
        LOG.debug(
            f'Setting zone {self.zone_info} volume to {amp_volume} (HA volume {volume}'
        )
        await self._amp.set_volume(self._zone_id, amp_volume)

    async def async_volume_up(self):
        LOG.debug(f'Volume up for zone {self.zone_info}')
        await self._amp.volume_up(self._zone_id, VOL_INCREMENT)

    async def async_volume_down(self):
        LOG.debug(f'Volume down for zone {self.zone_info}')
        await self._amp.volume_down(self._zone_id, VOL_INCREMENT)

    @property
    def icon(self):
        if self.state == STATE_OFF:
            return 'mdi:speaker-off'
        return 'mdi:speaker-multiple'
