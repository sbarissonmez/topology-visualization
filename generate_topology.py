import os
import json

from nornir import InitNornir
from nornir.plugins.tasks.networking import napalm_get

NORNIR_CONFIG_FILE = "config.yml"
OUTPUT_TOPOLOGY_FILENAME = 'topology.js'
CACHED_TOPOLOGY_FILENAME = 'cached_topology.json'
TOPOLOGY_FILE_HEAD = "\n\nvar topologyData = "

# Topology layers would be sorted
# in the same descending order
# as in the tuple below
NX_LAYER_SORT_ORDER = (
    'undefined',
    'outside',
    'edge-switch',
    'edge-router',
    'core-router',
    'core-switch',
    'distribution-router',
    'distribution-switch',
    'leaf',
    'spine',
    'access-switch'
)


nr = InitNornir(config_file=NORNIR_CONFIG_FILE)

icon_capability_map = {
    'router': 'router',
    'switch': 'switch',
    'bridge': 'switch',
    'station': 'host'


icon_model_map = {
    'CSR1000V': 'router',
    'Nexus': 'switch',
    'IOSXRv': 'router',
    'IOSv': 'switch',
    '2901': 'router',
    '2911': 'router',
    '2921': 'router',
    '2951': 'router',
    '4321': 'router',
    '4331': 'router',
    '4351': 'router',
    '4421': 'router',
    '4431': 'router',
    '4451': 'router',
    '2960': 'switch',
    '3750': 'switch',
    '3850': 'switch',
}


interface_full_name_map = {
    'Eth': 'Ethernet',
    'Fa': 'FastEthernet',
    'Gi': 'GigabitEthernet',
    'Te': 'TenGigabitEthernet',
}


def if_fullname(ifname):
    for k, v in interface_full_name_map.items():
        if ifname.startswith(v):
            return ifname
        if ifname.startswith(k):
            return ifname.replace(k, v)
    return ifname
    

def if_shortname(ifname):
    for k, v in interface_full_name_map.items():
        if ifname.startswith(v):
            return ifname.replace(v, k)
    return ifname


def get_icon_type(device_cap_name, device_model=''):
    """
    Device icon selection function. Selection order:
    - LLDP capabilities mapping.
    - Device model mapping.
    - Default 'unknown'.
    """
    if device_cap_name:
        icon_type = icon_capability_map.get(device_cap_name)
        if icon_type:
            return icon_type
    if device_model:
        # Check substring presence in icon_model_map keys
        # string until the first match
        for model_shortname, icon_type in icon_model_map.items():
            if model_shortname in device_model:
                return icon_type
    return 'unknown'


def get_node_layer_sort_preference(device_role):
    """Layer priority selection function
    Layer sort preference is designed as numeric value.
    This function identifies it by NX_LAYER_SORT_ORDER
    object position by default. With numeric values,
    the logic may be improved without changes on NeXt app side.
    0(null) results undefined layer position in NeXt UI.
    Valid indexes start with 1.
    """
    for i, role in enumerate(NX_LAYER_SORT_ORDER, start=1):
        if device_role == role:
            return i
    return 1


def get_host_data(task):
    """Nornir Task for data collection on target hosts."""
    task.run(
        task=napalm_get,
        getters=['facts', 'lldp_neighbors_detail']
    )


def normalize_result(nornir_job_result):
    """
    get_host_data result parser.
    Returns LLDP and FACTS data dicts
    with hostname keys.
    """
    global_lldp_data = {}
    global_facts = {}
    for device, output in nornir_job_result.items():
        if output[0].failed:
            # Write default data to dicts if the task is failed.
            # Use host inventory object name as a key.
            global_lldp_data[device] = {}
            global_facts[device] = {
                'nr_role': nr.inventory.hosts[device].get('role', 'undefined'),
                'nr_ip': nr.inventory.hosts[device].get('hostname', 'n/a'),
}
            continue
        # Use FQDN as unique ID for devices withing the script.
        device_fqdn = output[1].result['facts']['fqdn']
        if not device_fqdn:
            # If FQDN is not set use hostname.
            # LLDP TLV follows the same logic.
            device_fqdn = output[1].result['facts']['hostname']
        if not device_fqdn:
            # Use host inventory object name as a key if
            # neither FQDN nor hostname are set
            device_fqdn = device
        global_facts[device_fqdn] = output[1].result['facts']
        global_facts[device_fqdn]['nr_role'] = nr.inventory.hosts[device].get('role', 'undefined')
        global_facts[device_fqdn]['nr_ip'] = nr.inventory.hosts[device].get('hostname', 'n/a')
        global_lldp_data[device_fqdn] = output[1].result['lldp_neighbors_detail']
    return global_lldp_data, global_facts


def extract_lldp_details(lldp_data_dict):
    """
    LLDP data dict parser.
    Returns set of all the discovered hosts,
    LLDP capabilities dict with all LLDP-discovered host,
    and all discovered interconections between hosts.
    """
    discovered_hosts = set()
    lldp_capabilities_dict = {}
    global_interconnections = []
    for host, lldp_data in lldp_data_dict.items():
        if not host:
            continue
        discovered_hosts.add(host)
        if not lldp_data:
            continue
        for interface, neighbors in lldp_data.items():
            for neighbor in neighbors:
                if not neighbor['remote_system_name']:
                    continue
                discovered_hosts.add(neighbor['remote_system_name'])
                if neighbor['remote_system_enable_capab']:
                    # In case of multiple enable capabilities pick first in the list
                    lldp_capabilities_dict[neighbor['remote_system_name']] = (
                        neighbor['remote_system_enable_capab'][0]
                    )
                else:
                    lldp_capabilities_dict[neighbor['remote_system_name']] = ''
                # Store interconnections in a following format:
                # ((source_hostname, source_port), (dest_hostname, dest_port))
                local_end = (host, interface)
                remote_end = (
                    neighbor['remote_system_name'],
                    if_fullname(neighbor['remote_port'])
                )
                # Check if the link is not a permutation of already added one
                # (local_end, remote_end) equals (remote_end, local_end)
                link_is_already_there = (
                    (local_end, remote_end) in global_interconnections
                    or (remote_end, local_end) in global_interconnections
                )
                if link_is_already_there:
                    continue
                global_interconnections.append((
                    (host, interface),
                    (neighbor['remote_system_name'], if_fullname(neighbor['remote_port']))
                ))
    return [discovered_hosts, global_interconnections, lldp_capabilities_dict]


def generate_topology_json(*args):
    """
    JSON topology object genetator.
    Takes as an input:
    - discovered hosts set,
    - LLDP capabilities dict with hostname keys,
    - interconnections list,
    - facts dict with hostname keys.
    """
    discovered_hosts, interconnections, lldp_capabilities_dict, facts = args
    host_id = 0
    host_id_map = {}
    topology_dict = {'nodes': [], 'links': []}
    for host in discovered_hosts:
        device_model = 'n/a'
        device_serial = 'n/a'
        device_role = 'undefined'
        device_ip = 'n/a'
        if facts.get(host):
            device_model = facts[host].get('model', 'n/a')
            device_serial = facts[host].get('serial_number', 'n/a')
            device_role = facts[host].get('nr_role', 'undefined')
            device_ip = facts[host].get('nr_ip', 'n/a')
        host_id_map[host] = host_id
        topology_dict['nodes'].append({
            'id': host_id,
            'name': host,
            'primaryIP': device_ip,
            'model': device_model,
            'serial_number': device_serial,
            'layerSortPreference': get_node_layer_sort_preference(
                device_role
            ),
            'icon': get_icon_type(
                lldp_capabilities_dict.get(host, ''),
                device_model
            )
        })
        host_id += 1
    link_id = 0
    for link in interconnections:
        topology_dict['links'].append({
            'id': link_id,
            'source': host_id_map[link[0][0]],
            'target': host_id_map[link[1][0]],
            'srcIfName': if_shortname(link[0][1]),
            'srcDevice': link[0][0],
            'tgtIfName': if_shortname(link[1][1]),
            'tgtDevice': link[1][0],
        })
        link_id += 1
    return topology_dict


def write_topology_file(topology_json, header=TOPOLOGY_FILE_HEAD, dst=OUTPUT_TOPOLOGY_FILENAME):
    with open(dst, 'w') as topology_file:
        topology_file.write(header)
        topology_file.write(json.dumps(topology_json, indent=4, sort_keys=True))
        topology_file.write(';')


def write_topology_cache(topology_json, dst=CACHED_TOPOLOGY_FILENAME):
    with open(dst, 'w') as cached_file:
        cached_file.write(json.dumps(topology_json, indent=4, sort_keys=True))


def read_cached_topology(filename=CACHED_TOPOLOGY_FILENAME):
    if not os.path.exists(filename):
        return {}
    if not os.path.isfile(filename):
        return {}
    cached_topology = {}
    with open(filename, 'r') as file:
        try:
            cached_topology = json.loads(file.read())
        except ValueError as err:
            print(f"Failed to read cache from {filename}: {err}")
            return {}
        except Exception as err:
            print(f"Failed to read cache from {filename}: {err}")
            return {}
    return cached_topology