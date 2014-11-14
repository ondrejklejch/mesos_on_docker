#!/bin/bash

python create_config.py > /etc/haproxy/haproxy.cfg
haproxy -f /etc/haproxy/haproxy.cfg
