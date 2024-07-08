# Home assistant integration for Pulse-Eight ProAudio matrix

Provides Pulse-Eight ProAudio matrix support to Home Assistant.  

Protocol: https://support.pulse-eight.com/helpdesk/attachments/30049880171

Heavily inspired by / borrowed from https://github.com/rsnodgrass/hass-xantech/tree/master


## Installation
Copy into custom_components

## Sample Configuration in configuration.yaml
```
media_player:
  - platform: pulse_eight
    host: "10.0.50.166"
    port: "50005"
    zones:
      4:
        name: "Garage"
      24:
        name: "Boat House"
    sources:
      18:
        name: "Spotify"
      19:
        name: "Alexa"

logger:
  logs:
    custom_components.pulse_eight: debug
```
