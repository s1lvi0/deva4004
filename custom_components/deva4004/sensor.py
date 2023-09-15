import logging
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pysnmp.hlapi import *
from .snmp_data import _get_monitor_data, _get_alarms_data
from .const import *
import socket

_LOGGER = logging.getLogger(__name__)

async def update_listener(hass, entry):
    logging.debug("optionsdeva4004: " + str(entry.options.get(CONF_POLL_INTERVAL_DATA)))
    coordinators = hass.data[DOMAIN]
    
    # Update the intervals of the coordinators
    coordinators["coordinator"].update_interval = timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL_DATA))
    coordinators["alarms_coordinator"].update_interval = timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL_ALARMS))
    
class Deva4004DataUpdateCoordinator(DataUpdateCoordinator):
    def update_interval(self, update_interval):
        self.update_interval = timedelta(seconds=update_interval)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    entities = []

    data = config_entry.data["device_data"]
    ip_address = config_entry.data.get("ip_address")
    port = config_entry.data.get("port")
    read_community = config_entry.data.get("read_community")

    monitoring_data = {}

    async def async_update_data():
        try:
            return await _get_monitor_data(ip_address, port, read_community, BASE_OID_MONITORING , monitoring_data)
        except Exception as e:
            raise UpdateFailed(f"Update failed: {e}")
        
    async def async_update_alarms_data():
        try:
            return await _get_alarms_data(ip_address, port, read_community)
        except Exception as e:
            raise UpdateFailed(f"Update failed: {e}")
        
    data_update_interval = config_entry.options.get(CONF_POLL_INTERVAL_DATA, DEFAULT_POLL_INTERVAL_DATA)
    alarms_update_interval = config_entry.options.get(CONF_POLL_INTERVAL_ALARMS, DEFAULT_POLL_INTERVAL_ALARMS)

    coordinator = Deva4004DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=data_update_interval),
    )

    alarms_coordinator = Deva4004DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="alarms",
        update_method=async_update_alarms_data,
        update_interval=timedelta(seconds=alarms_update_interval),
    )

    hass.data[DOMAIN] = {
        "coordinator": coordinator,
        "alarms_coordinator": alarms_coordinator
    }

    await coordinator.async_refresh()
    await alarms_coordinator.async_refresh()

    for device_data in data[0]:
        if int(device_data["active"]) != 4:
            deva4004_device_data = Deva4004DeviceData(hass, device_data)
            entities.extend([
                Deva4004ChannelSensor(coordinator, deva4004_device_data),
                Deva4004ActiveSensor(coordinator, deva4004_device_data),
                Deva4004AcqTimeSensor(coordinator, deva4004_device_data),
                Deva4004FrequencySensor(coordinator, deva4004_device_data),
                Deva4004RfLevelSensor(coordinator, deva4004_device_data),
                Deva4004MpxLevelSensor(coordinator, deva4004_device_data),
                Deva4004PilotLevelSensor(coordinator, deva4004_device_data),
                Deva4004RdsLevelSensor(coordinator, deva4004_device_data),
                Deva4004RightLevelSensor(coordinator, deva4004_device_data),
                Deva4004LeftLevelSensor(coordinator, deva4004_device_data),
                Deva4004RdsPiSensor(coordinator, deva4004_device_data),
                Deva4004RdsPsSensor(coordinator, deva4004_device_data),
                Deva4004RdsRtSensor(coordinator, deva4004_device_data),
                Deva4004RfAlarmSensor(alarms_coordinator, deva4004_device_data),
                Deva4004MpxAlarmSensor(alarms_coordinator, deva4004_device_data),
                Deva4004PilotAlarmSensor(alarms_coordinator, deva4004_device_data),
                Deva4004RdsAlarmSensor(alarms_coordinator, deva4004_device_data),
            ])

    async_add_entities(entities, True)

class Deva4004DeviceData:
    def __init__(self, hass, data):
        self.hass = hass
        self.data = data

class Deva4004SensorBase(Entity):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        self.coordinator = coordinator
        self.device_data = device_data
        self.frequency = device_data.data["frequency"]
        self.channel_number = device_data.data["channel_number"]
        self._unsub = None

    @property
    def should_poll(self):
        return False

    @property
    def available(self):
        return self.coordinator.data is not None
    
    @property
    def name(self):
        return self.device_data.data["name"]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self.device_data.data["name"]) + "_" + self.device_data.data['channel_number'])},
            "name": self.device_data.data["name"],
            "manufacturer": "Deva Broadcast",
            "model": "Deva4004",
            "configuration_url": "http://" + self.device_data.data["name"],
            "sw_version":self.device_data.data["fw_version"],
            "hw_version":self.device_data.data["serial_number"],
        }
    async def async_added_to_hass(self):
        self._unsub = self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
       if self._unsub:
            self._unsub()

class Deva4004ChannelSensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{super().name} Channel"

    @property
    def state(self):
        return (int(self.device_data.data["channel_number"]) + 1)

    @property
    def unique_id(self):
        return f"{self.device_data.data['name']}-channel-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:format-list-numbered"

class Deva4004ActiveSensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{super().name} Active"

    @property
    def state(self):
        return antenna_dict.get(int(self.device_data.data["active"]))

    @property
    def unique_id(self):
        return f"{self.device_data.data['name']}-active-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:antenna"

class Deva4004FrequencySensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{super().name} Frequency"

    @property
    def state(self):
        return (int(self.device_data.data["frequency"])/1000)
    
    @property
    def unit_of_measurement(self):
        return "MHz"

    @property
    def unique_id(self):
        return f"{self.device_data.data['name']}-frequency-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:radio-tower"
    
class Deva4004AcqTimeSensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{super().name} Acquisition Time"

    @property
    def state(self):
        return self.device_data.data["acq_time"]
    
    @property
    def unit_of_measurement(self):
        return "s"

    @property
    def unique_id(self):
        return f"{self.device_data.data['name']}-acq_time-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:clock-time-five-outline"

class Deva4004RfLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RF Level"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("rf_level", None)

    @property
    def unique_id(self):
        return f"rf_level_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:signal'

    @property
    def unit_of_measurement(self):
        return "dBμV"


class Deva4004MpxLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} MPX Level"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("mpx_level", None)

    @property
    def unique_id(self):
        return f"mpx_level_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:waveform'

    @property
    def unit_of_measurement(self):
        return "kHz"

class Deva4004PilotLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} Pilot Level"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("pilot_level", None)

    @property
    def unique_id(self):
        return f"pilot_level_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:cosine-wave'

    @property
    def unit_of_measurement(self):
        return "kHz"

class Deva4004RdsLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RDS Level"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("rds_level", None)

    @property
    def unique_id(self):
        return f"rds_level_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:rename'

    @property
    def unit_of_measurement(self):
        return "kHz"

class Deva4004RightLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} Right Level"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("right_level", None)

    @property
    def unique_id(self):
        return f"right_level_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alpha-r'

    @property
    def unit_of_measurement(self):
        return "dB"

class Deva4004LeftLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} Left Level"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("left_level", None)

    @property
    def unique_id(self):
        return f"left_level_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alpha-l'

    @property
    def unit_of_measurement(self):
        return "dB"

class Deva4004RdsPiSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RDS PI"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("rds_pi", None)

    @property
    def unique_id(self):
        return f"rds_pi_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:identifier'

class Deva4004RdsPsSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RDS PS"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("rds_ps", None)

    @property
    def unique_id(self):
        return f"rds_ps_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:text-short'

class Deva4004RdsRtSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RDS RT"

    @property
    def state(self):
        frequency = self.device_data.data["frequency"]
        return self.coordinator.data.get(frequency, {}).get("rds_rt", None)

    @property
    def unique_id(self):
        return f"rds_rt_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:text'

class Deva4004RfAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RF Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_rf", None)))

    @property
    def unique_id(self):
        return f"alarm_rf_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'

class Deva4004MpxAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} MPX Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_mpx", None)))

    @property
    def unique_id(self):
        return f"alarm_mpx_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'
    
class Deva4004PilotAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} Pilot Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_pilot", None)))

    @property
    def unique_id(self):
        return f"alarm_pilot_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'
    
class Deva4004RdsAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{super().name} RDS Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_rds", None)))

    @property
    def unique_id(self):
        return f"alarm_rds_{self.device_data.data['name']}_{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'

