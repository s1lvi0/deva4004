import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .snmp_data import _get_monitor_data, _get_alarms_data
from .const import *
import socket

_LOGGER = logging.getLogger(__name__)

async def update_listener(hass, entry):
    _LOGGER.warning(f"[DEVA4004] update_listener called with data interval: {entry.options.get(CONF_POLL_INTERVAL_DATA)}")
    coordinators = hass.data[DOMAIN][entry.entry_id]

    # Update the intervals of the coordinators - need to call async_set_update_interval
    await coordinators["coordinator"].async_set_update_interval(timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL_DATA)))
    await coordinators["alarms_coordinator"].async_set_update_interval(timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL_ALARMS)))

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    entities = []

    data = config_entry.data["device_data"]
    ip_address = config_entry.data.get("ip_address")
    port = config_entry.data.get("port")
    read_community = config_entry.data.get("read_community")
    instance_name = config_entry.data.get("name")

    monitoring_data = {}

    async def async_update_data():
        try:
            _LOGGER.warning(f"[DEVA4004] Before poll: monitoring_data id={id(monitoring_data)}, has {len(monitoring_data)} freq(s): {list(monitoring_data.keys())}")
            result = await _get_monitor_data(ip_address, port, read_community, BASE_OID_MONITORING , monitoring_data)
            _LOGGER.warning(f"[DEVA4004] After poll: monitoring_data id={id(monitoring_data)}, has {len(monitoring_data)} freq(s): {list(monitoring_data.keys())}")
            _LOGGER.warning(f"[DEVA4004] Result id={id(result)}, has {len(result)} freq(s): {list(result.keys())}")
            _LOGGER.warning(f"[DEVA4004] Are they same object? {result is monitoring_data}")
            return result
        except Exception as e:
            raise UpdateFailed(f"Update failed: {e}")
        
    async def async_update_alarms_data():
        try:
            return await _get_alarms_data(ip_address, port, read_community)
        except Exception as e:
            raise UpdateFailed(f"Update failed: {e}")
        
    data_update_interval = config_entry.options.get(CONF_POLL_INTERVAL_DATA, DEFAULT_POLL_INTERVAL_DATA)
    alarms_update_interval = config_entry.options.get(CONF_POLL_INTERVAL_ALARMS, DEFAULT_POLL_INTERVAL_ALARMS)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=data_update_interval),
    )

    alarms_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="alarms",
        update_method=async_update_alarms_data,
        update_interval=timedelta(seconds=alarms_update_interval),
    )

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][config_entry.entry_id] = {
        "coordinator": coordinator,
        "alarms_coordinator": alarms_coordinator
    }

    await coordinator.async_refresh()
    await alarms_coordinator.async_refresh()

    for device_data in data[0]:
        if int(device_data["active"]) != 4:
            deva4004_device_data = Deva4004DeviceData(hass, device_data, instance_name)
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
    def __init__(self, hass, data, instance_name):
        self.hass = hass
        self.data = data
        self.instance_name = instance_name

class Deva4004SensorBase(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator)
        self.device_data = device_data
        self.frequency = device_data.data["frequency"]
        self.channel_number = device_data.data["channel_number"]

    @property
    def available(self):
        return self.coordinator.data is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self.device_data.data["name"]) + "_" + self.device_data.data['channel_number'])},
            "name": self.device_data.data["name"],
            "manufacturer": "Deva Broadcast",
            "model": "Deva4004",
            "configuration_url": "http://" + self.device_data.data["name"],
            "sw_version": self.device_data.data["fw_version"],
            "hw_version": self.device_data.data["serial_number"],
        }

class Deva4004ChannelSensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Channel"

    @property
    def state(self):
        return (int(self.device_data.data["channel_number"]) + 1)

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-channel-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:format-list-numbered"

class Deva4004ActiveSensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Active"

    @property
    def state(self):
        return antenna_dict.get(int(self.device_data.data["active"]))

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-active-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:antenna"

class Deva4004FrequencySensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Frequency"

    @property
    def state(self):
        return (int(self.device_data.data["frequency"])/1000)
    
    @property
    def unit_of_measurement(self):
        return "MHz"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-frequency-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:radio-tower"
    
class Deva4004AcqTimeSensor(Deva4004SensorBase):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Acquisition Time"

    @property
    def state(self):
        return self.device_data.data["acq_time"]
    
    @property
    def unit_of_measurement(self):
        return "s"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-acq_time-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:clock-time-five-outline"

class Deva4004RfLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RF Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        if self.coordinator.data:
            _LOGGER.warning(f"[DEVA4004] RF Sensor: Looking for freq {frequency} in {list(self.coordinator.data.keys())}, found: {frequency in self.coordinator.data}")
        return self.coordinator.data.get(frequency, {}).get("rf_level", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rf_level-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:signal'

    @property
    def unit_of_measurement(self):
        return "dBμV"

    @property
    def state_class(self):
        return "measurement"


class Deva4004MpxLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} MPX Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("mpx_level", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-mpx_level-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:waveform'

    @property
    def unit_of_measurement(self):
        return "kHz"

    @property
    def state_class(self):
        return "measurement"

class Deva4004PilotLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Pilot Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("pilot_level", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-pilot_level-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:cosine-wave'

    @property
    def unit_of_measurement(self):
        return "kHz"

    @property
    def state_class(self):
        return "measurement"

class Deva4004RdsLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_level", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_level-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:rename'

    @property
    def unit_of_measurement(self):
        return "kHz"

    @property
    def state_class(self):
        return "measurement"

class Deva4004RightLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Right Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("right_level", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-right_level-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alpha-r'

    @property
    def unit_of_measurement(self):
        return "dB"

    @property
    def state_class(self):
        return "measurement"

class Deva4004LeftLevelSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Left Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("left_level", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-left_level-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alpha-l'

    @property
    def unit_of_measurement(self):
        return "dB"

    @property
    def state_class(self):
        return "measurement"

class Deva4004RdsPiSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS PI"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_pi", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_pi-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:identifier'

class Deva4004RdsPsSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS PS"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_ps", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_ps-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:text-short'

class Deva4004RdsRtSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS RT"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_rt", None) if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_rt-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:text'

class Deva4004RfAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RF Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_rf", None)))

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_rf-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'

class Deva4004MpxAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} MPX Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_mpx", None)))

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_mpx-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'
    
class Deva4004PilotAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Pilot Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_pilot", None)))

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_pilot-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'
    
class Deva4004RdsAlarmSensor(Deva4004SensorBase):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator, device_data)

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS Alarm"

    @property
    def state(self):
        channel_number = int(self.device_data.data["channel_number"])
        return alarm_dict.get(int(self.coordinator.data.get(channel_number, {}).get("alarm_rds", None)))

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_rds-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:alert-outline'

