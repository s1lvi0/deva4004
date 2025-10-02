from pysnmp.hlapi.v3arch.asyncio import get_cmd, bulk_walk_cmd, bulk_cmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity
from .const import *
import numpy as np
import logging

_LOGGER = logging.getLogger(__name__)

def fr8p8_to_value(fr8p8_value):
    return np.round(int(fr8p8_value) / 256, 1)

async def _get_oid(host: str, port: int, community: str, oid: str):
    error = None
    result = None

    try:
        error_indication, error_status, error_index, var_binds = await get_cmd(
            SnmpEngine(),
            CommunityData(community, mpModel=0),
            await UdpTransportTarget.create((host, port)),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )

        if error_indication:
            print(f"SNMP connection error: ", error_indication)
            error = str(error_indication)
        elif error_status:
            print(f"SNMP error: {error_status.prettyPrint()}")
            error = str(error_status.prettyPrint())
        else:
            result = var_binds[0][1].prettyPrint() if var_binds else None

    except Exception as e:
        print(f"Exception in SNMP connection: ", e)
        error = str(e)

    return result, error

async def _get_snmp_subtree(host: str, port: int, community: str, base_oid: str):
    subtree = []
    error = None

    try:
        async for (error_indication,
                   error_status,
                   error_index,
                   var_binds) in bulk_walk_cmd(
                       SnmpEngine(),
                       CommunityData(community, mpModel=0),
                       await UdpTransportTarget.create((host, port), timeout=10.0, retries=1),
                       ContextData(),
                       0, 50,
                       ObjectType(ObjectIdentity(base_oid)),
                       lexicographicMode=False
                   ):
            if error_indication:
                print(f"SNMP connection error: ", error_indication)
                error = str(error_indication)
                raise Exception(error)  # Throw an exception when an error occurs
            elif error_status:
                print(f"SNMP connection error: ", '%s at %s' % (error_status.prettyPrint(), var_binds[int(error_index)-1] if error_index else '?'))
                error = str(error_status)
                raise Exception(error)  # Throw an exception when an error occurs
            else:
                for var_bind in var_binds:
                    oid, value = [x.prettyPrint() for x in var_bind]
                    subtree.append(value)

    except Exception as e:
        print(f"SNMP connection error: ", e)
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

async def _get_monitor_data(host, port, community, base_oid, freq_data):
    _LOGGER.debug(f"Starting monitor data poll. Currently tracking {len(freq_data)} frequencies: {list(freq_data.keys())}")

    frequency = None
    updated_frequency = None
    async for errorIndication, errorStatus, errorIndex, varBinds in bulk_walk_cmd(
        SnmpEngine(),
        CommunityData(community, mpModel=0),
        await UdpTransportTarget.create((host, port)),
        ContextData(),
        0, 5,
        ObjectType(ObjectIdentity(base_oid)),
        lookupMib=False,
        lexicographicMode=False
    ):
        if errorIndication:  # SNMP engine errors
            _LOGGER.error(f"SNMP error indication: {errorIndication}")
            continue
        elif errorStatus:  # SNMP agent errors
            _LOGGER.error('%s at %s' % (errorStatus.prettyPrint(), varBinds[int(errorIndex) - 1] if errorIndex else '?'))
            continue
        else:
            for varBind in varBinds:  # SNMP response contents
                oid, value = [x.prettyPrint() for x in varBind]
                if oid == OID_FREQ_MONITOR:  # if this is the frequency OID
                    frequency = value
                    updated_frequency = frequency
                    if frequency not in freq_data:  # if this frequency is not already a key in the dictionary
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

    if updated_frequency:
        _LOGGER.warning(f"[DEVA4004] Updated freq {updated_frequency}, data: {freq_data[updated_frequency]}")
    else:
        _LOGGER.warning("[DEVA4004] No frequency data received in this poll")

    _LOGGER.warning(f"[DEVA4004] Poll complete. Total frequencies: {len(freq_data)}, keys: {list(freq_data.keys())}")
    return freq_data

async def _get_alarms_data(host: str, port: int, community: str):
    alarm_data = {}
    alarm_rf, error = await _get_snmp_subtree(host, port, community, BASE_OID_ALARM_RF)
    alarm_mpx, error = await _get_snmp_subtree(host, port, community, BASE_OID_ALARM_MPX)
    alarm_pilot, error = await _get_snmp_subtree(host, port, community, BASE_OID_ALARM_PILOT)
    alarm_rds, error = await _get_snmp_subtree(host, port, community, BASE_OID_ALARM_RDS)

    for i in range(0, 50):
        alarm_data[i] = {
            "alarm_rf": alarm_rf[i],
            "alarm_mpx": alarm_mpx[i],
            "alarm_pilot": alarm_pilot[i],
            "alarm_rds": alarm_rds[i]
        }

    return alarm_data