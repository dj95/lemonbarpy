#!/usr/bin/env python3
#
# lemonbarpy
#
# (c) 2016 Daniel Jankowski


import os
import sys
import json
import signal


import bspwm


CONFIG_FILE = '/home/neo/Projekte/Python/lemonbarpy/conf/lemonbarpy.json'


# TODO: remove this dirty solution
BAR = None


"""
@description
    Shutdown handler to shut down the bar gracefully.
"""
def sigint_handler(signal, frame):
    BAR.shutdown()
    sys.exit(0)


"""
@description
    Reads the json config file for color configuration.
"""
def get_config():
    if not os.path.isfile(CONFIG_FILE):
        return False

    with open(CONFIG_FILE, 'r') as fp:
        data = json.loads(fp.read())
    return data


def main():
    b = bspwm.BSPWM(get_config())

    global BAR
    BAR = b

    signal.signal(signal.SIGINT, sigint_handler)
    
    b.draw_bar()


if __name__ == '__main__':
    main()
