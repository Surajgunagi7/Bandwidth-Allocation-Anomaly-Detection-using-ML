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
import time

def topology(start_collector=False,traffic=False):
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

        topology_file = Path(__file__).resolve()
        repo_root = topology_file.parents[1]
        collector_path = repo_root / "mininet" / "collector.py"

        iface = "ap1-wlan1"
        backend_url = "http://localhost:5000/traffic"   # ← FIXED: reachable from Mininet
        capture_dir = "/tmp/captures"

        # Ensure dirs exist
        ap1.cmd(f"mkdir -p {capture_dir}/{{incoming,sent,failed}}")

        if collector_path.exists():
            cmd = (
                f"python3 {collector_path} "
                f"--iface {iface} "
                f'--backend "{backend_url}" '
                f"--capture-dir {capture_dir} "
                f"--rotate-secs 3 "
                f"&"
            )
            info(f"Running: {cmd}\n")
            ap1.cmd(cmd)
        else:
            info(f"Collector not found: {collector_path}\n")

    if traffic:
        info("*** Waiting 5s for backend + collector readiness\n")
        time.sleep(5)
        start_test_traffic(net, duration=180)

    info("*** Running CLI\n   ")
    CLI(net)

    info("*** Shutting down collector...\n")
    ap1.cmd("pkill -f collector.py || true")
    time.sleep(3)

    info("*** Stopping network\n")
    net.stop()

def start_test_traffic(net, duration=180):
    """
    Demo traffic for bandwidth ML testing
    - sta1: High TCP bulk
    - sta2: Medium HTTP bursts
    - sta3: Low steady UDP
    """

    info("*** Starting ML demo traffic\n")

    sta1 = net.get('sta1')
    sta2 = net.get('sta2')
    sta3 = net.get('sta3')
    h1 = net.get('h1')

    # Cleanup
    h1.cmd("pkill -f iperf || true")
    h1.cmd("pkill -f http.server || true")

    # Start servers
    h1.cmd("iperf -s -D")
    h1.cmd("iperf -s -u -D")
    h1.cmd("python3 -m http.server 80 &")

    # 🔴 sta1 — High bandwidth TCP bulk
    sta1.cmd(
        f"iperf -c {h1.IP()} -t {duration} -i 1 &"
    )

    # 🟡 sta2 — Medium HTTP-like traffic
    sta2.cmd(
        f"while true; do "
        f"wget -O /dev/null http://{h1.IP()}:80 || true; "
        f"sleep 1.5; "
        f"done &"
    )

    # 🟢 sta3 — Low steady UDP
    sta3.cmd(
        f"iperf -u -c {h1.IP()} -b 512K -t {duration} &"
    )

    info("*** Demo traffic started\n")


if __name__ == '__main__':
    setLogLevel('info')
    topology(start_collector=True,traffic=True)