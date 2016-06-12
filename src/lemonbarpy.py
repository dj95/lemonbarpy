#!/usr/bin/env python3
#
# lemonbarpy
#
# (c) 2016 Daniel Jankowski


import os
import sys
import json
import signal
import argparse


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
def get_config(config_file):
    if not os.path.isfile(config_file):
        return False

    with open(config_file, 'r') as fp:
        data = json.loads(fp.read())
    return data


def main():
    parser= argparse.ArgumentParser()
    parser.add_argument('-c', '--config', type=str, help='Specify a config file')
    args = parser.parse_args()

    if args.config:
        b = bspwm.BSPWM(get_config(args.config))
    else:
        b = bspwm.BSPWM(get_config(CONFIG_FILE))

    global BAR
    BAR = b

    signal.signal(signal.SIGINT, sigint_handler)
    
    b.draw_bar()


if __name__ == '__main__':
    main()
