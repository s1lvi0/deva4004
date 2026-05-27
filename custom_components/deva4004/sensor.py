import logging
import re
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from .snmp_data import _get_monitor_data, _get_alarms_data, _get_logger_data
from .const import *

_LOGGER = logging.getLogger(__name__)


async def update_listener(hass, entry):
    _LOGGER.debug("update_listener called with data interval: %s", entry.options.get(CONF_POLL_INTERVAL_DATA))
    coordinators = hass.data[DOMAIN][entry.entry_id]
    await coordinators["coordinator"].async_set_update_interval(timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL_DATA)))
    await coordinators["alarms_coordinator"].async_set_update_interval(timedelta(seconds=entry.options.get(CONF_POLL_INTERVAL_ALARMS)))


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    ip_address = config_entry.data.get("ip_address")
    port = config_entry.data.get("port")
    read_community = config_entry.data.get("read_community")
    instance_name = config_entry.data.get("name")

    engine = await hass.async_add_executor_job(SnmpEngine)

    try:
        data = await _get_logger_data(engine, ip_address, port, read_community)
    except Exception as e:
        raise ConfigEntryNotReady(f"Failed to fetch device data from {ip_address}: {e}") from e

    monitoring_data = {}

    async def async_update_data():
        try:
            return await _get_monitor_data(engine, ip_address, port, read_community, BASE_OID_MONITORING, monitoring_data)
        except Exception as e:
            raise UpdateFailed(f"Update failed: {e}")

    async def async_update_alarms_data():
        try:
            return await _get_alarms_data(engine, ip_address, port, read_community)
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
        "alarms_coordinator": alarms_coordinator,
        "engine": engine,
    }

    await coordinator.async_refresh()
    await alarms_coordinator.async_refresh()

    entities = []
    for device_data in data[0]:
        if int(device_data["active"]) != 4:
            deva4004_device_data = Deva4004DeviceData(hass, device_data, instance_name, ip_address)
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
    def __init__(self, hass, data, instance_name, ip_address):
        self.hass = hass
        self.data = data
        self.instance_name = instance_name
        self.ip_address = ip_address


class Deva4004SensorBase(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator: DataUpdateCoordinator, device_data: Deva4004DeviceData):
        super().__init__(coordinator)
        self.device_data = device_data

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, str(self.device_data.data["name"]) + "_" + self.device_data.data['channel_number'])},
            "name": self.device_data.data["name"],
            "manufacturer": "Deva Broadcast",
            "model": "Deva4004",
            "configuration_url": f"http://{self.device_data.ip_address}",
            "sw_version": self.device_data.data["fw_version"],
            "hw_version": self.device_data.data["serial_number"],
        }


class Deva4004StaticSensor(Deva4004SensorBase):
    # Value comes from the config-time device_data snapshot, not the coordinator
    @property
    def available(self):
        return True


class Deva4004FrequencyKeyedSensor(Deva4004SensorBase):
    # Value comes from coordinator.data keyed by the channel's frequency
    @property
    def available(self):
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return False
        return str(self.device_data.data["frequency"]) in self.coordinator.data


class Deva4004ChannelKeyedSensor(Deva4004SensorBase):
    # Value comes from coordinator.data keyed by the channel's index (alarms)
    @property
    def available(self):
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return False
        try:
            return int(self.device_data.data["channel_number"]) in self.coordinator.data
        except (TypeError, ValueError):
            return False


class Deva4004ChannelSensor(Deva4004StaticSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Channel"

    @property
    def state(self):
        return int(self.device_data.data["channel_number"]) + 1

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-channel-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:format-list-numbered"


class Deva4004ActiveSensor(Deva4004StaticSensor):
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


class Deva4004FrequencySensor(Deva4004StaticSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Frequency"

    @property
    def state(self):
        return int(self.device_data.data["frequency"]) / 1000

    @property
    def unit_of_measurement(self):
        return "MHz"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-frequency-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return "mdi:radio-tower"


class Deva4004AcqTimeSensor(Deva4004StaticSensor):
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


class Deva4004RfLevelSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RF Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rf_level") if self.coordinator.data else None

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


class Deva4004MpxLevelSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} MPX Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("mpx_level") if self.coordinator.data else None

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


class Deva4004PilotLevelSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Pilot Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("pilot_level") if self.coordinator.data else None

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


class Deva4004RdsLevelSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_level") if self.coordinator.data else None

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


class Deva4004RightLevelSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Right Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("right_level") if self.coordinator.data else None

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


class Deva4004LeftLevelSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Left Level"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("left_level") if self.coordinator.data else None

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


class Deva4004RdsPiSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS PI"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_pi") if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_pi-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:identifier'


class Deva4004RdsPsSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS PS"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_ps") if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_ps-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:text-short'


class Deva4004RdsRtSensor(Deva4004FrequencyKeyedSensor):
    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS RT"

    @property
    def state(self):
        frequency = str(self.device_data.data["frequency"])
        return self.coordinator.data.get(frequency, {}).get("rds_rt") if self.coordinator.data else None

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-rds_rt-{self.device_data.data['channel_number']}"

    @property
    def icon(self):
        return 'mdi:text'


class Deva4004AlarmSensorBase(Deva4004ChannelKeyedSensor):
    alarm_key = ""
    alarm_type = ""
    level_kind = ""

    @property
    def state(self):
        if self.coordinator.data is None:
            return None
        try:
            channel_number = int(self.device_data.data["channel_number"])
        except (TypeError, ValueError):
            return None
        value = self.coordinator.data.get(channel_number, {}).get(self.alarm_key)
        if value is None:
            return None
        try:
            return alarm_dict.get(int(value), alarm_dict["default"])
        except (TypeError, ValueError):
            return alarm_dict["default"]

    @property
    def icon(self):
        return 'mdi:alert-outline'

    @property
    def extra_state_attributes(self):
        instance = self.device_data.instance_name or ""
        try:
            freq_mhz = int(self.device_data.data["frequency"]) / 1000
        except (TypeError, ValueError):
            freq_mhz = None
        # SNMP returns station name like "103.0 KISS"; drop the frequency prefix
        # so messages don't read "103.0 MHz - 103.0 KISS".
        station_name = self.device_data.data.get("name") or ""
        station_name = re.sub(r"^\d+(\.\d+)?\s+", "", station_name)
        level_entity_id = None
        if self.entity_id and self.level_kind:
            suffix = f"_{self.level_kind}_alarm"
            replacement = f"_{self.level_kind}_level"
            if self.entity_id.endswith(suffix):
                level_entity_id = self.entity_id[: -len(suffix)] + replacement
        return {
            "location": instance.replace("DEVA_", "").replace("_", " "),
            "frequency_mhz": freq_mhz,
            "station_name": station_name,
            "alarm_type": self.alarm_type,
            "level_entity_id": level_entity_id,
            "level_unit": "dBμV" if self.level_kind == "rf" else "kHz",
        }


class Deva4004RfAlarmSensor(Deva4004AlarmSensorBase):
    alarm_key = "alarm_rf"
    alarm_type = "RF"
    level_kind = "rf"

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RF Alarm"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_rf-{self.device_data.data['channel_number']}"


class Deva4004MpxAlarmSensor(Deva4004AlarmSensorBase):
    alarm_key = "alarm_mpx"
    alarm_type = "MPX"
    level_kind = "mpx"

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} MPX Alarm"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_mpx-{self.device_data.data['channel_number']}"


class Deva4004PilotAlarmSensor(Deva4004AlarmSensorBase):
    alarm_key = "alarm_pilot"
    alarm_type = "Pilot"
    level_kind = "pilot"

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} Pilot Alarm"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_pilot-{self.device_data.data['channel_number']}"


class Deva4004RdsAlarmSensor(Deva4004AlarmSensorBase):
    alarm_key = "alarm_rds"
    alarm_type = "RDS"
    level_kind = "rds"

    @property
    def name(self):
        return f"{self.device_data.instance_name} {self.device_data.data['name']} RDS Alarm"

    @property
    def unique_id(self):
        return f"{self.device_data.instance_name}-{self.device_data.data['name']}-alarm_rds-{self.device_data.data['channel_number']}"
