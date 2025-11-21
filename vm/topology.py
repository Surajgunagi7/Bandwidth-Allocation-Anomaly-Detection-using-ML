#!/usr/bin/python

"""
Mininet-WiFi Topology Script
- 1 Access Point (AP)
- 3 Wireless Stations
- 1 Wired Host
- Optional Controller
- All nodes can communicate via pingall
"""

from mininet.node import Controller, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
import os
from pathlib import Path

def topology(start_collector=False):
    """Create a custom topology with AP, stations, wired host, and controller"""
    
    info("*** Creating network\n")
    net = Mininet_wifi(
        controller=Controller,
        accessPoint=OVSKernelAP,
        switch=OVSKernelSwitch,
        link=wmediumd,
        wmediumd_mode=interference
    )

    info("*** Adding controller\n")
    c0 = net.addController('c0', controller=Controller, port=6653)

    info("*** Adding Access Point\n")
    ap1 = net.addAccessPoint(
        'ap1',
        ssid='wifi-mininwt-dev',
        mode='g',
        channel='1',
        position='50,50,0',
        range=30
    )

    info("*** Adding Stations\n")
    sta1 = net.addStation(
        'sta1',
        ip='10.0.0.1/24',
        position='30,50,0'
    )
    sta2 = net.addStation(
        'sta2',
        ip='10.0.0.2/24',
        position='50,30,0'
    )
    sta3 = net.addStation(
        'sta3',
        ip='10.0.0.3/24',
        position='70,50,0'
    )

    info("*** Adding Wired Host\n")
    h1 = net.addHost(
        'h1',
        ip='10.0.0.4/24'
    )

    info("*** Configuring WiFi nodes\n")
    net.configureWifiNodes()

    # Link wired host to AP
    net.addLink(h1, ap1)

    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])

    # AUTO-START COLLECTOR ON AP1
    # --------------------------------------------------------------

    if start_collector:
        info("*** Starting collector on AP1\n")

        # repo_root = parent of the directory containing this file
        topology_file = Path(__file__).resolve()
        repo_root = topology_file.parents[1]     # moves from repo_root/vm → repo_root

        collector_path = repo_root / "vm" / "collector.py"

        iface = "ap1-wlan1"
        backend_url = "http://127.0.0.1:5000/traffic"
        capture_dir = "/tmp/captures"

        if collector_path.exists():
            cmd = (
                f"python3 {collector_path} "
                f"--iface {iface} "
                f'--backend "{backend_url}" '
                f"--capture-dir {capture_dir} "
                f"&"
            )
            info(f"Running on AP1: {cmd}\n")
            ap1.cmd(cmd)
        else:
            info(f"Collector script NOT found at: {collector_path}\n")

    info("*** Testing connectivity\n")
    net.pingAll()

    info("*** Running CLI\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology(start_collector=True)