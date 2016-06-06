#!/usr/bin/env python3
#
# dbus-spotify
#
# (c) 2016 Daniel Jankowski


import sys
import dbus
import time
import socket


from threading import Thread, Event


class SpotifyThread(Thread):

    def __init__(self):
        super().__init__()

        self.stop_event = Event()

    def get_spotify_metadata(self):
        try:
            bus = dbus.SessionBus()
            proxy = bus.get_object('org.mpris.MediaPlayer2.spotify','/org/mpris/MediaPlayer2')
            properties_manager = dbus.Interface(proxy, 'org.freedesktop.DBus.Properties')
            metadata = properties_manager.Get('org.mpris.MediaPlayer2.Player', 'Metadata')
        except Exception as e:
            return None
        return metadata

    def run(self):
        last_playing = ''
        was_none = False
        while not self.stop_event.is_set():
            # Spotify      
            metadata = self.get_spotify_metadata()
            if metadata is not None:
                try:
                    current_playing = metadata['xesam:title'] + ' - ' + metadata['xesam:artist'][0] + '(' + metadata['xesam:album'] + ')'
                    if current_playing != last_playing:
                        sys.stdout.write('UTILS' + current_playing)
                        sys.stdout.flush()
                        was_none = False
                    last_playing = current_playing
                except:
                    continue
            else:
                if not was_none:
                    sys.stdout.write('UTILSNone')
                    sys.stdout.flush()
                    was_none = True
            
            self.stop_event.wait(0.1)


class KeyboardThread(Thread):

    def __init__(self):
        super().__init__()

        self.stop_event = Event()

        self.__socket = socket.socket(socket.AF_UNIX, socket.SOCK_RAW)
        self.__socket.bind('/dev/shm/lemonbarpy.socket')
        self.__socket.settimeout(0.1)

    def run(self):
        last_playing = ''
        while not self.stop_event.is_set():
            # Keyboard shortcuts
            try:
                data = self.__socket.recv(1024)
            except:
                continue
            ws = data.decode('utf-8')
            sys.stdout.write(ws)
            sys.stdout.flush()

            #self.stop_event.wait(0.1)


def main():
    spotify_thread = SpotifyThread()
    keyboard_thread = KeyboardThread()

    spotify_thread.start()
    keyboard_thread.start()


if __name__ == '__main__':
    main()
