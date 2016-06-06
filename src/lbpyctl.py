#!/usr/bin/env python3
#
# lemonbarpy
#
# (c) 2016 Daniel Jankowski


import socket
import argparse


ALLOWED_COMMANDS = ['wlan', 'eth', 'vol', 'bat', 'date', 'vpn', 'spotify']


def send_command(command):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.connect('/dev/shm/lemonbarpy.socket')
    s.send('CMD{0}'.format(command).encode('utf-8'))
    s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    args = parser.parse_args()

    if args.command in ALLOWED_COMMANDS:
        send_command(args.command)


if __name__ == '__main__':
    main()
