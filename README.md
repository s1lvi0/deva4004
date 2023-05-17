DEVA 4004 Home Assistant Custom Component
This repository contains the DEVA 4004 custom component for Home Assistant. The DEVA 4004 component allows you to interact with the DEVA 4004 device via the SNMP protocol within your Home Assistant setup.

Configuration
The configuration is done via the Home Assistant UI where you can input the device's IP address, port, and the SNMP community for read operations.

Installation
Clone this repository or download the source code as a zip file and extract it in your /config/custom_components/ directory. If the directory does not exist, create it first.
Restart Home Assistant to load the component.
Go to the "Integration" page available in your Home Assistant dashboard's configuration panel.
Click on the "+ ADD INTEGRATION" button, search for "DEVA 4004", and fill in the required fields.
Required Information
CONF_NAME: The name of the DEVA 4004 device (default: "DEVA4004").
CONF_IP_ADDRESS: The IP address of the DEVA 4004 device (default: "192.168.100.37").
CONF_PORT: The port to be used (default: 161).
CONF_READ_COMMUNITY: The SNMP community for read operations (default: "DEVA4004").
Options
CONF_POLL_INTERVAL_DATA: The interval between data polls in seconds (default: 3).
CONF_POLL_INTERVAL_ALARMS: The interval between alarm polls in seconds (default: 90).
These options can be adjusted in the options flow for the DEVA 4004 integration after it has been added.

Constants
The const.py file contains all the constants which are used in the DEVA 4004 Home Assistant custom component. Some key constants include:

OID_FW_VERSION: The OID for the firmware version.
OID_SERIAL_VERSION: The OID for the serial version.
BASE_OID_MONITORING: The base OID for monitoring data.
OID_FREQ_MONITOR: The OID for frequency monitoring.
See const.py for a full list of constants and their descriptions.

Errors
Errors during setup or updates are shown in the Home Assistant log.

Contributions
Contributions to this repository are welcome. Please fork this project, create a new branch for your proposed changes, and open a pull request.

License
This project is released under the MIT License.

Disclaimer
This project is not affiliated, associated, authorized, endorsed by, or in any way officially connected with the DEVA Broadcast Ltd, or any of its subsidiaries or its affiliates. The name "DEVA 4004" as well as related names, marks, emblems, and images are registered trademarks of their respective owners.

Support
Please use GitHub issues for questions, issues and feature requests. Thanks!