#!/usr/bin/env python3
#
# lemonbarpy
#
# (c) 2016 Daniel Jankowski


import os
import json


import bspwm


CONFIG_FILE = '/home/neo/Projekte/Python/lemonbarpy/conf/lemonbarpy.json'


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
    b.draw_bar()
    pass


if __name__ == '__main__':
    main()
