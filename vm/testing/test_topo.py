#!/usr/bin/env python3
# run_topo_tests.py — automated tests for the Mininet-WiFi topology
# Usage: sudo python3 run_topo_tests.py

import time
import os
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mininet.node import Controller

def build_net():
    net = Mininet_wifi(controller=Controller, accessPoint=OVSKernelAP,
                       link=wmediumd, wmediumd_mode=interference)
    c0 = net.addController('c0')
    ap1 = net.addAccessPoint('ap1', ssid='myNetwork', mode='g', channel='1',
                             position='50,50,0', range=40)
    sta1 = net.addStation('sta1', ip='10.0.0.1/24', position='45,50,0')
    sta2 = net.addStation('sta2', ip='10.0.0.2/24', position='50,45,0')
    sta3 = net.addStation('sta3', ip='10.0.0.3/24', position='55,50,0')
    h1 = net.addHost('h1', ip='10.0.0.10/24')
    net.configureWifiNodes()
    net.addLink(h1, ap1)
    net.build()
    c0.start()
    ap1.start([c0])
    return net

def run_tests(net):
    print("Running pingAll...")
    net.pingAll()

    # start iperf3 server on h1
    h1 = net.get('h1')
    sta1 = net.get('sta1')
    sta2 = net.get('sta2')
    sta3 = net.get('sta3')

    print("Starting iperf3 server on h1")
    h1.cmd('iperf3 -s -D')  # daemonize server

    print("TCP test: sta1 -> h1")
    out = sta1.cmd('iperf3 -c 10.0.0.10 -t 8 -J')   # JSON output (if iperf3 supports)
    print(out[:500])

    print("Simultaneous TCP test (sta1, sta2, sta3)")
    sta1.cmd('iperf3 -c 10.0.0.10 -t 10 > /tmp/sta1_tcp.log &')
    sta2.cmd('iperf3 -c 10.0.0.10 -t 10 > /tmp/sta2_tcp.log &')
    sta3.cmd('iperf3 -c 10.0.0.10 -t 10 > /tmp/sta3_tcp.log &')
    time.sleep(12)
    for i, s in enumerate((sta1,sta2,sta3), start=1):
        print(f"--- sta{i} tcp log ---")
        print(s.cmd('tail -n 8 /tmp/sta%d_tcp.log' % i))

    print("UDP test: sta1 -> h1 (5 Mbps)")
    print(sta1.cmd('iperf3 -u -b 5M -c 10.0.0.10 -t 8'))

    # capture brief pcap on ap (needs tcpdump)
    ap1 = net.get('ap1')
    pcap_wlan = '/tmp/ap_wlan.pcap'
    print("Capturing 5s pcap on ap1-wlan1 ->", pcap_wlan)
    ap1.cmd('timeout 5 tcpdump -nn -i ap1-wlan1 -w %s &' % pcap_wlan)
    time.sleep(6)
    print("pcap saved:", pcap_wlan, "size:", os.path.getsize(pcap_wlan) if os.path.exists(pcap_wlan) else 'missing')

def cleanup(net):
    print("Stopping network")
    net.stop()

if __name__ == '__main__':
    net = build_net()
    try:
        run_tests(net)
    finally:
        cleanup(net)
