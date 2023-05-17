from pysnmp.hlapi import *
import time

BASE_OID_NAME = ".1.3.6.1.4.1.35833.10.2.5.2.1.4"
BASE_OID_ACTIVE_INACTIVE = ".1.3.6.1.4.1.35833.10.2.5.2.1.2"
BASE_OID_FREQUENCY_MHZ = ".1.3.6.1.4.1.35833.10.2.5.2.1.3"
BASE_OID_CHANNEL_NUMBER = ".1.3.6.1.4.1.35833.10.2.5.2.1.1"
BASE_OID_ACQ_TIME = ".1.3.6.1.4.1.35833.10.2.5.2.1.5"
OID_FW_VERSION = ".1.3.6.1.4.1.35833.10.1.1.0"

def _get_snmp_subtree(host: str, port: int, community: str, base_oid: str):
    subtree = []
    error = None

    try:
        for (error_indication,
             error_status,
             error_index,
             var_binds) in bulkCmd(SnmpEngine(),
                                   CommunityData(community, mpModel=0),
                                   UdpTransportTarget((host, port)),
                                   ContextData(),
                                   0, 50,
                                   ObjectType(ObjectIdentity(base_oid)),
                                   lookupMib=False,
                                   lexicographicMode=False):
            for var_bind in var_binds:
                oid, value = [x.prettyPrint() for x in var_bind]
                subtree.append(value)

    except Exception as e:
        print(f"SNMP connection error: ", e)
        error = str(e)

    return subtree[:-1]

def get_alarms_data(host: str, port: int, community: str):
    alarm_data = {}
    alarm_rf = _get_snmp_subtree(host, port, community,'.1.3.6.1.4.1.35833.10.4.14.1.2')
    alarm_mpx = _get_snmp_subtree(host, port, community,'.1.3.6.1.4.1.35833.10.4.14.1.3')
    alarm_pilot = _get_snmp_subtree(host, port, community,'.1.3.6.1.4.1.35833.10.4.14.1.5')
    alarm_rds = _get_snmp_subtree(host, port, community,'.1.3.6.1.4.1.35833.10.4.14.1.6')

    for i in range(1, 51):
        alarm_data[i] = {
            "alarm_rf": alarm_rf[i-1],
            "alarm_mpx": alarm_mpx[i-1],
            "alarm_pilot": alarm_pilot[i-1],
            "alarm_rds": alarm_rds[i-1]
        }

    return alarm_data

data = get_alarms_data("192.168.100.37", 161, "DEVA4004")
print(data)

# def get_bulk_data(host, port, community, base_oid, freq_data):

#     iterator = bulkCmd(SnmpEngine(),
#                                 CommunityData(community, mpModel=0),
#                                 UdpTransportTarget((host, port)),
#                                 ContextData(),
#                                 0, 5,
#                                 ObjectType(ObjectIdentity(base_oid)),
#                                 lookupMib=False,
#                                 lexicographicMode=False)

#     frequency = None
#     for errorIndication, errorStatus, errorIndex, varBinds in iterator:
#         if errorIndication:  # SNMP engine errors
#             print(errorIndication)
#             continue
#         elif errorStatus:  # SNMP agent errors
#             print('%s at %s' % (errorStatus.prettyPrint(), varBinds[int(errorIndex) - 1] if errorIndex else '?'))
#             continue
#         else:           
#             for varBind in varBinds:  # SNMP response contents
#                 oid, value = [x.prettyPrint() for x in varBind]
#                 if oid == '1.3.6.1.4.1.35833.10.4.13.0':  # if this is the frequency OID
#                     frequency = value
#                     if frequency not in freq_data :  # if this frequency is not already a key in the dictionary
#                         freq_data[frequency] = {} 
#                 elif oid == '1.3.6.1.4.1.35833.10.4.1.0':
#                     freq_data[frequency]['rf_level'] = value
#                 elif oid == '1.3.6.1.4.1.35833.10.4.2.0':
#                     freq_data[frequency]['mpx_level'] = value
#                 elif oid == '1.3.6.1.4.1.35833.10.4.3.0':
#                     freq_data[frequency]['left_level'] = value
#                 # elif oid == '1.3.6.1.4.1.35833.10.3.24.0':
#                 #     freq_data[frequency]['right_level'] = value
#                 # elif oid == '1.3.6.1.4.1.35833.10.3.15.0':
#                 #     freq_data[frequency]['pilot_level'] = value
#                 # elif oid == '1.3.6.1.4.1.35833.10.3.18.0':
#                 #     freq_data[frequency]['rds_level'] = value

#     return freq_data


# freq_data = {}
# for i in range(2):
#     data = get_bulk_data("192.168.100.37", 161, "DEVA4004", '.1.3.6.1.4.1.35833.10.4', freq_data)
#     time.sleep(2) 

# for frequency, values in data.items():
#     print(f"Frequency: {frequency}")
#     for key, value in values.items():
#         print(f"  {key}: {value}")
#     print()  # print a blank line between frequencies

# freq_data = {}
# freq_data[103.2] = {'rf_level': -30, 'mpx_level': 5}
# freq_data[103.2]['rds_level'] = 15
# print(freq_data)

# def _get_snmp(host: str, port: int, community: str, oid: str):
#     error = None
#     result = None

#     try:
#         error_indication, error_status, error_index, var_binds = next(
#             getCmd(SnmpEngine(),
#                    CommunityData(community, mpModel=0),
#                    UdpTransportTarget((host, port)),
#                    ContextData(),
#                    ObjectType(ObjectIdentity(oid))))

#         if error_indication:
#             print(f"SNMP connection error: ", error_indication)
#             error = str(error_indication)
#         elif error_status:
#             print(f"SNMP error: {error_status.prettyPrint()}")
#             error = str(error_status.prettyPrint())
#         else:
#             result = var_binds[0][1].prettyPrint() if var_binds else None

#     except Exception as e:
#         print(f"Exception in SNMP connection: ", e)
#         error = str(e)

#     return result, error



# def _get_snmp_subtree(host: str, port: int, community: str, base_oid: str):
#     subtree = []
#     error = None

#     try:
#         for (error_indication,
#              error_status,
#              error_index,
#              var_binds) in bulkCmd(SnmpEngine(),
#                                    CommunityData(community, mpModel=0),
#                                    UdpTransportTarget((host, port)),
#                                    ContextData(),
#                                    0, 50,
#                                    ObjectType(ObjectIdentity(base_oid)),
#                                    lexicographicMode=False):
#             for var_bind in var_binds:
#                 subtree.append(str(var_bind).split('= ')[-1])

#     except Exception as e:
#         print(f"SNMP connection error: ", e)
#         error = str(e)

#     return subtree[:-1], error


# def _get_logger_data(host: str, port: int, community: str):
#     data_and_errors = [
#         _get_snmp_subtree(host, port, community, BASE_OID_NAME),
#         _get_snmp_subtree(host, port, community, BASE_OID_ACTIVE_INACTIVE),
#         _get_snmp_subtree(host, port, community, BASE_OID_FREQUENCY_MHZ),
#         _get_snmp_subtree(host, port, community, BASE_OID_CHANNEL_NUMBER),
#         _get_snmp_subtree(host, port, community, BASE_OID_ACQ_TIME),
#     ]
    
#     data = zip(*[d for d, _ in data_and_errors])
#     errors = [e for _, e in data_and_errors if e is not None]
    
#     return [
#         dict(zip(("name", "active", "frequency", "channel_number", "acq_time"), values))
#         for values in data
#     ], errors


# data, errors = _get_logger_data("192.168.100.37", 161, "DEVA4004")
# print(data)
# print(errors)

# fw = _get_snmp("192.168.100.37", 161, "DEVA4004", OID_FW_VERSION)
# print(fw[0])

# for ch in data:
#     print(str(ch["name"]) + " - " + str(ch["active"]) +  " - " + str(ch["frequency"]) + " - " + str(ch["acq_time"]))

# data = []
# devices = 50
# for idx in range(devices):
#     data.append(_get_logger_data("192.168.100.37", 161, "DEVA4004",idx))

# for idx in range(devices):
#     print(data[idx]["name"])
#     print(data[idx]["channel_number"])
#     print(data[idx]["active"])
#     print(data[idx]["frequency"])
#     print("------------------")
