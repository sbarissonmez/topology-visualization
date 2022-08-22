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
