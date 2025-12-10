#!/usr/bin/python
"""
Mininet-WiFi Topology for Dataset Generation
Simplified version without collector - for training data collection only
"""
from mininet.node import Controller, OVSKernelSwitch
from mininet.log import setLogLevel, info
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
import time

def dataset_topology():
    """Create simple topology for dataset generation"""
    
    info("*** Creating network for dataset generation\n")
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
        ssid='dataset-gen-network',
        mode='g',
        channel='1',
        position='50,50,0',
        range=50
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
    info("*** Linking host to AP\n")
    net.addLink(h1, ap1)
    
    info("*** Starting network\n")
    net.build()
    c0.start()
    ap1.start([c0])
    
    # Wait for network to stabilize
    info("*** Waiting for network to stabilize (5s)\n")
    time.sleep(5)
    
    # Test basic connectivity
    info("*** Testing connectivity\n")
    result = sta1.cmd('ping -c 3 10.0.0.4')
    if '0 received' not in result:
        info("✓ Network connectivity OK\n")
    else:
        info("⚠ Warning: Connectivity issues detected\n")
        info(f"Ping result: {result}\n")
    
    info("\n" + "="*60 + "\n")
    info("*** Network ready for dataset generation\n")
    info("="*60 + "\n")
    info("Stations:\n")
    info("  sta1 = 10.0.0.1\n")
    info("  sta2 = 10.0.0.2\n")
    info("  sta3 = 10.0.0.3\n")
    info("Host:\n")
    info("  h1   = 10.0.0.4\n")
    info("AP Interface:\n")
    info("  ap1-wlan1 (use this for tcpdump)\n")
    info("="*60 + "\n")
    
    # Keep network running (no CLI - for automation)
    try:
        info("*** Keeping network alive (Ctrl+C to stop)\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        info('\n*** Stopping network\n')
        net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    dataset_topology()