from pysnmp.hlapi import *
from .const import *
import numpy as np

def fr8p8_to_value(fr8p8_value):
    return np.round(int(fr8p8_value) / 256, 1)

def _get_oid(host: str, port: int, community: str, oid: str):
    error = None
    result = None

    try:
        error_indication, error_status, error_index, var_binds = next(
            getCmd(SnmpEngine(),
                   CommunityData(community, mpModel=0),
                   UdpTransportTarget((host, port)),
                   ContextData(),
                   ObjectType(ObjectIdentity(oid))))

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

def _get_snmp_subtree(host: str, port: int, community: str, base_oid: str):
    subtree = []
    error = None

    try:
        for (error_indication,
             error_status,
             error_index,
             var_binds) in bulkCmd(SnmpEngine(),
                                   CommunityData(community, mpModel=0),
                                   UdpTransportTarget((host, port), timeout=10.0, retries=1),  # Adjust timeout and retries here
                                   ContextData(),
                                   0, 50,
                                   ObjectType(ObjectIdentity(base_oid)),
                                   lexicographicMode=False):
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

    return subtree[:-1], error



def _get_logger_data(host: str, port: int, community: str):
    data_and_errors = [
        _get_snmp_subtree(host, port, community, BASE_OID_NAME),
        _get_snmp_subtree(host, port, community, BASE_OID_ACTIVE_INACTIVE),
        _get_snmp_subtree(host, port, community, BASE_OID_FREQUENCY_MHZ),
        _get_snmp_subtree(host, port, community, BASE_OID_CHANNEL_NUMBER),
        _get_snmp_subtree(host, port, community, BASE_OID_ACQ_TIME),
    ]

    fw_version, fw_version_error = _get_oid(host, port, community, OID_FW_VERSION)
    serial_number, serial_number_error = _get_oid(host, port, community, OID_SERIAL_VERSION)

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

    iterator = bulkCmd(SnmpEngine(),
                                CommunityData(community, mpModel=0),
                                UdpTransportTarget((host, port)),
                                ContextData(),
                                0, 5,
                                ObjectType(ObjectIdentity(base_oid)),
                                lookupMib=False,
                                lexicographicMode=False)

    frequency = None
    for errorIndication, errorStatus, errorIndex, varBinds in iterator:
        if errorIndication:  # SNMP engine errors
            print(errorIndication)
            continue
        elif errorStatus:  # SNMP agent errors
            print('%s at %s' % (errorStatus.prettyPrint(), varBinds[int(errorIndex) - 1] if errorIndex else '?'))
            continue
        else:           
            for varBind in varBinds:  # SNMP response contents
                oid, value = [x.prettyPrint() for x in varBind]
                if oid == OID_FREQ_MONITOR:  # if this is the frequency OID
                    frequency = value
                    if frequency not in freq_data :  # if this frequency is not already a key in the dictionary
                        freq_data[frequency] = {} 
                elif oid == OID_RF_LEVEL:
                    freq_data[frequency]['rf_level'] = fr8p8_to_value(value)
                elif oid == OID_MPX_LEVEL:
                    freq_data[frequency]['mpx_level'] = fr8p8_to_value(value)
                elif oid == OID_LEFT_LEVEL:
                    freq_data[frequency]['left_level'] = fr8p8_to_value(value)
                elif oid == OID_RIGHT_LEVEL:
                    freq_data[frequency]['right_level'] = fr8p8_to_value(value)
                elif oid == OID_PILOT_LEVEL:
                    freq_data[frequency]['pilot_level'] = fr8p8_to_value(value)
                elif oid == OID_RDS_LEVEL:
                    freq_data[frequency]['rds_level'] = fr8p8_to_value(value)
                elif oid == OID_RDS_PI:
                    freq_data[frequency]['rds_pi'] = str(value)
                elif oid == OID_RDS_PS:
                    freq_data[frequency]['rds_ps'] = str(value)
                elif oid == OID_RDS_RT:
                    freq_data[frequency]['rds_rt'] = str(value)

    return freq_data

async def _get_alarms_data(host: str, port: int, community: str):
    alarm_data = {}
    alarm_rf, error = _get_snmp_subtree(host, port, community, BASE_OID_ALARM_RF)
    alarm_mpx, error = _get_snmp_subtree(host, port, community, BASE_OID_ALARM_MPX)
    alarm_pilot, error = _get_snmp_subtree(host, port, community, BASE_OID_ALARM_PILOT)
    alarm_rds, error = _get_snmp_subtree(host, port, community, BASE_OID_ALARM_RDS)

    for i in range(0, 50):
        alarm_data[i] = {
            "alarm_rf": alarm_rf[i],
            "alarm_mpx": alarm_mpx[i],
            "alarm_pilot": alarm_pilot[i],
            "alarm_rds": alarm_rds[i]
        }

    return alarm_data