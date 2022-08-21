# Topology Visualization

An automated topology visualization solution based on LLDP data.

NAPALM is used along with Nornir to retrieve the data from hosts:
  - NAPALM GET_LLDP_NEIGHBORS_DETAILS getter returns LLDP neighbors details;
  - NAPALM GET_FACTS getter returns general device info we can use for visualization.

The script accepts an initialized Nornir as an input. Mandatory items:
  - IP-addresses of network devices;
  - Valid credentials with read-only access to those devices.

The script output consists of:
  - topology.js file with JS topology objects for NeXt UI;
  - cached_topology.json file with JSON-representation of the analyzed topology.
  - diff_topology.js file with visualized topology changes as
    compared to last known cached_topology.json.
  - Console output of the topology diff check result.

The script implements general error handling and data normalization.
Data collection attempt runs on all the nodes in Nornir inventory.
A standalone node with Nornir host object name is included to
resulting topology in case of any errors.

Open main.html to view current topology.
Open diff_page.html or use navigation buttons on main.html to view changes.