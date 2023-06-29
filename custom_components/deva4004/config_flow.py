from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
import voluptuous as vol
from .snmp_data import _get_logger_data
import ipaddress
from .const import *

def valid_ip_or_hostname(host):
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        try:
            socket.gethostbyname(host)
            return host
        except socket.gaierror:
            raise ValueError("Invalid IP or hostname")

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_READ_COMMUNITY, default=DEFAULT_READ_COMMUNITY): cv.string,
        # vol.Optional(CONF_WRITE_COMMUNITY, default=DEFAULT_WRITE_COMMUNITY): cv.string,
    }
)

class Deva4004OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_POLL_INTERVAL_DATA, default=self.config_entry.options.get(CONF_POLL_INTERVAL_DATA, DEFAULT_POLL_INTERVAL_DATA)): vol.All(int, vol.Range(min=10)),
                vol.Required(CONF_POLL_INTERVAL_ALARMS, default=self.config_entry.options.get(CONF_POLL_INTERVAL_ALARMS, DEFAULT_POLL_INTERVAL_ALARMS)): vol.All(int, vol.Range(min=60)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)

class Deva4004ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        host = user_input[CONF_IP_ADDRESS]
        name = user_input[CONF_NAME]
        port = user_input[CONF_PORT]
        community = user_input[CONF_READ_COMMUNITY]

        DATA_SCHEMA_COMPILED = vol.Schema(
            {
                vol.Required(CONF_NAME, default=name): cv.string,
                vol.Required(CONF_IP_ADDRESS,default=host): str,
                vol.Required(CONF_PORT, default=port): int,
                vol.Required(CONF_READ_COMMUNITY, default=community): cv.string,
            }
        )

        try:
            if not (1 <= port <= 65535):
                raise ValueError("Invalid port number.")
        except ValueError as e:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA_COMPILED, errors={"base": str(e)})

        try:
            data = await self.hass.async_add_executor_job(_get_logger_data, host, port, community)
        except Exception as e:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA_COMPILED, errors={"base": str(e)})

        if data is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA_COMPILED, errors={"base": "No data in the device"})

        user_input["device_data"] = data

        return self.async_create_entry(title=name, data=user_input)
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return Deva4004OptionsFlowHandler(config_entry)
