from pysnmp.hlapi.v3arch.asyncio import get_cmd, bulk_walk_cmd, bulk_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
from .const import *
import numpy as np
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

# Note: SNMP engine is created per-thread in executor functions to avoid event loop blocking
# The MIB loading warnings are expected but harmless since operations run in thread executors

def fr8p8_to_value(fr8p8_value):
    return np.round(int(fr8p8_value) / 256, 1)

async def _get_oid(host: str, port: int, community: str, oid: str):
    error = None
    result = None

    try:
        snmp_engine = SnmpEngine()
        error_indication, error_status, error_index, var_binds = await get_cmd(
            snmp_engine,
            CommunityData(community, mpModel=0),
            await UdpTransportTarget.create((host, port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lookupMib=False
        )

        if error_indication:
            _LOGGER.debug(f"SNMP timeout/error: {error_indication}")
            error = str(error_indication)
        elif error_status:
            _LOGGER.debug(f"SNMP error: {error_status.prettyPrint()}")
            error = str(error_status.prettyPrint())
        else:
            result = var_binds[0][1].prettyPrint() if var_binds else None

    except Exception as e:
        _LOGGER.debug(f"SNMP exception: {e}")
        error = str(e)

    return result, error

async def _get_snmp_subtree(host: str, port: int, community: str, base_oid: str):
    subtree = []
    error = None

    try:
        snmp_engine = SnmpEngine()
        async for (error_indication,
                   error_status,
                   error_index,
                   var_binds) in bulk_walk_cmd(
                       snmp_engine,
                       CommunityData(community, mpModel=0),
                       await UdpTransportTarget.create((host, port), timeout=10.0, retries=1),
                       ContextData(),
                       0, 50,
                       ObjectType(ObjectIdentity(base_oid)),
                       lookupMib=False,
                       lexicographicMode=False
                   ):
            if error_indication:
                _LOGGER.debug(f"SNMP timeout/error: {error_indication}")
                error = str(error_indication)
                raise Exception(error)
            elif error_status:
                _LOGGER.debug(f"SNMP error: {error_status.prettyPrint()}")
                error = str(error_status)
                raise Exception(error)
            else:
                for var_bind in var_binds:
                    oid, value = [x.prettyPrint() for x in var_bind]
                    subtree.append(value)

    except Exception as e:
        _LOGGER.debug(f"SNMP error: {e}")
        error = str(e)
        raise

    return subtree, error



async def _get_logger_data(host: str, port: int, community: str):
    data_and_errors = [
        await _get_snmp_subtree(host, port, community, BASE_OID_NAME),
        await _get_snmp_subtree(host, port, community, BASE_OID_ACTIVE_INACTIVE),
        await _get_snmp_subtree(host, port, community, BASE_OID_FREQUENCY_MHZ),
        await _get_snmp_subtree(host, port, community, BASE_OID_CHANNEL_NUMBER),
        await _get_snmp_subtree(host, port, community, BASE_OID_ACQ_TIME),
    ]

    fw_version, fw_version_error = await _get_oid(host, port, community, OID_FW_VERSION)
    serial_number, serial_number_error = await _get_oid(host, port, community, OID_SERIAL_VERSION)

    # Duplicate the fw_version to match the length of other data arrays
    fw_version_array = (fw_version,) * len(data_and_errors[0][0])
    serial_number_array = (serial_number,) * len(data_and_errors[0][0])

    data_and_errors.append((fw_version_array, fw_version_error))
    data_and_errors.append((serial_number_array, serial_number_error))


    data = zip(*[d for d, _ in data_and_errors])
    errors = [e for _, e in data_and_errors if e is not None]

    return [
        dict(zip(("name", "active", "frequency", "channel_number", "acq_time", "fw_version", "serial_number"), values))
        for values in data
    ], errors

def _sync_get_monitor_data(host, port, community, base_oid, freq_data):
    """Synchronous version to run in executor."""
    import asyncio
    from pysnmp.hlapi.v3arch.asyncio import get_cmd, bulk_walk_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity

    frequency = None
    updated_frequency = None

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async def _do_walk():
            nonlocal frequency, updated_frequency
            snmp_engine = SnmpEngine()
            try:
                async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
                    snmp_engine,
                    CommunityData(community, mpModel=0),
                    await UdpTransportTarget.create((host, port)),
                    ContextData(),
                    0, 5,
                    ObjectType(ObjectIdentity(base_oid)),
                    lookupMib=False,
                    lexicographicMode=False
                ):
                    if errorIndication:
                        _LOGGER.debug(f"SNMP timeout/error: {errorIndication}")
                        continue
                    elif errorStatus:
                        _LOGGER.debug(f"SNMP error: {errorStatus.prettyPrint()}")
                        continue
                    else:
                        for varBind in varBinds:
                            oid, value = [x.prettyPrint() for x in varBind]
                            if oid == OID_FREQ_MONITOR:
                                frequency = value
                                updated_frequency = frequency
                                if frequency not in freq_data:
                                    freq_data[frequency] = {}
                                    _LOGGER.info(f"New frequency detected: {frequency}")
                            elif oid == OID_RF_LEVEL:
                                if frequency:
                                    freq_data[frequency]['rf_level'] = fr8p8_to_value(value)
                            elif oid == OID_MPX_LEVEL:
                                if frequency:
                                    freq_data[frequency]['mpx_level'] = fr8p8_to_value(value)
                            elif oid == OID_LEFT_LEVEL:
                                if frequency:
                                    freq_data[frequency]['left_level'] = fr8p8_to_value(value)
                            elif oid == OID_RIGHT_LEVEL:
                                if frequency:
                                    freq_data[frequency]['right_level'] = fr8p8_to_value(value)
                            elif oid == OID_PILOT_LEVEL:
                                if frequency:
                                    freq_data[frequency]['pilot_level'] = fr8p8_to_value(value)
                            elif oid == OID_RDS_LEVEL:
                                if frequency:
                                    freq_data[frequency]['rds_level'] = fr8p8_to_value(value)
                            elif oid == OID_RDS_PI:
                                if frequency:
                                    freq_data[frequency]['rds_pi'] = str(value)
                            elif oid == OID_RDS_PS:
                                if frequency:
                                    freq_data[frequency]['rds_ps'] = str(value)
                            elif oid == OID_RDS_RT:
                                if frequency:
                                    freq_data[frequency]['rds_rt'] = str(value)
            finally:
                # Properly close the SNMP engine
                snmp_engine.close_dispatcher()

        loop.run_until_complete(_do_walk())

        if updated_frequency:
            _LOGGER.debug(f"Updated freq {updated_frequency}")

        return freq_data
    finally:
        loop.close()

async def _get_monitor_data(host, port, community, base_oid, freq_data):
    """Async wrapper that runs the sync version in an executor."""
    _LOGGER.debug(f"Starting monitor data poll. Currently tracking {len(freq_data)} frequencies: {list(freq_data.keys())}")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_get_monitor_data, host, port, community, base_oid, freq_data)

def _sync_get_alarms_data(host: str, port: int, community: str):
    """Synchronous version to run in executor."""
    import asyncio
    from pysnmp.hlapi.v3arch.asyncio import bulk_walk_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity

    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        async def _do_get_alarms():
            alarm_data = {}
            snmp_engine = SnmpEngine()

            try:
                async def _get_subtree(base_oid):
                    subtree = []
                    async for (error_indication, error_status, error_index, var_binds) in bulk_walk_cmd(
                        snmp_engine,
                        CommunityData(community, mpModel=0),
                        await UdpTransportTarget.create((host, port), timeout=10.0, retries=1),
                        ContextData(),
                        0, 50,
                        ObjectType(ObjectIdentity(base_oid)),
                        lookupMib=False,
                        lexicographicMode=False
                    ):
                        if error_indication:
                            _LOGGER.debug(f"SNMP timeout/error: {error_indication}")
                            raise Exception(str(error_indication))
                        elif error_status:
                            _LOGGER.debug(f"SNMP error: {error_status.prettyPrint()}")
                            raise Exception(str(error_status))
                        else:
                            for var_bind in var_binds:
                                oid, value = [x.prettyPrint() for x in var_bind]
                                subtree.append(value)
                    return subtree

                alarm_rf = await _get_subtree(BASE_OID_ALARM_RF)
                alarm_mpx = await _get_subtree(BASE_OID_ALARM_MPX)
                alarm_pilot = await _get_subtree(BASE_OID_ALARM_PILOT)
                alarm_rds = await _get_subtree(BASE_OID_ALARM_RDS)

                for i in range(0, 50):
                    alarm_data[i] = {
                        "alarm_rf": alarm_rf[i],
                        "alarm_mpx": alarm_mpx[i],
                        "alarm_pilot": alarm_pilot[i],
                        "alarm_rds": alarm_rds[i]
                    }

                return alarm_data
            finally:
                # Properly close the SNMP engine
                snmp_engine.close_dispatcher()

        return loop.run_until_complete(_do_get_alarms())
    finally:
        loop.close()

async def _get_alarms_data(host: str, port: int, community: str):
    """Async wrapper that runs the sync version in an executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_get_alarms_data, host, port, community)