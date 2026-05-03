#!/bin/bash

# SENTINEL Macvlan Setup
# This script creates a macvlan interface on the host so the host 
# can communicate with the honeypot containers.

IFACE="wlan0"
SUBNET="192.168.0.0/24"
GATEWAY="192.168.0.1"
HOST_IP="192.168.0.200" # Dedicated IP for the host on the macvlan bridge

echo "[*] Setting up macvlan bridge for $IFACE..."

# Create the macvlan interface
ip link add sentinel-br link $IFACE type macvlan mode bridge

# Assign IP and bring it up
ip addr add $HOST_IP/24 dev sentinel-br
ip link set sentinel-br up

# Route traffic to the honeypot range through this interface
# Honeypots are 192.168.0.201 - 192.168.0.207
ip route add 192.168.0.200/29 dev sentinel-br

echo "[+] Macvlan setup complete. Host can now reach honeypots at 192.168.0.201+"
