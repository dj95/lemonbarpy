#!/usr/bin/env python3
#
# bspwm.py
#
# (c) 2016 Daniel Jankowski


import gi
import os
import re
import sys
import json
import select
import socket
import _thread
import netifaces
import subprocess


gi.require_version('Notify', '0.7')
from gi.repository import Notify


import utils


I3STATUS_PATH = '/opt/i3status/i3status'
I3STATUS_CONFIG = '/home/neo/Projekte/Python/lemonbarpy/conf/i3status.conf'


class BSPWM(object):

    def __init__(self, colors):
        super().__init__()

        # Save config
        self.__colors = colors

        # Start lemonbar in a subprocess
        self.__bar = subprocess.Popen(['lemonbar', '-B', colors['bg'], '-F', colors['fg'], '-f', "Terminesspowerline-8", '-f', "Ionicons-10", '-f', 'Icons-8', '-f', 'FontAwesome-10', '-f', "Serif-9", '-a', '30' ], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # Init notifier for displaying volume stats with dunst
        Notify.init('bar')

        # Panel variables to save intermediate states 
        self.__calendar = None
        self.__volume = None
        self.__vpn = None
        self.__state = None
        self.__spotify = None
        self.spotify_callback_value = None
        self.keyboard_callback_value = None
        self.status = {'date':'', 'spotify':'', 'vol':'', 'wlan':'', 'eth':'', 'vpn':'', 'bat':''}
        self.workspaces = ''
        self.title = ''
        self.current_power = ''
        self.old_power = ''
        
        # Status toggles
        self.__show_eth = False
        self.__show_wlan = False
        self.__show_battery = False
        self.__show_spotify = False


        self.__run = True

    """
    @description
        Returns a json object with all information about the root tree of bspwm.
    """
    def get_tree(self):
        s = subprocess.Popen(['bspc', 'query', '-T', '-d'], stdout=subprocess.PIPE)
        data = json.loads(s.communicate()[0].decode('utf-8'))
        return data

    """
    @description
        Generates the status line and writes it into lemonbar.
    """
    def draw_bar(self):
        # WM selection
        if self.__colors['wm'] == 'i3':
            import i3ipc

            self.__socket = i3ipc.Connection()

            self.__socket.on("workspace", self.trigger_i3_workspaces)
            self.__socket.on("window", self.trigger_i3_workspaces)
            # Start i3 main in seperate thread
            #NOTE: Otherwise it blocks the whole status
            _thread.start_new_thread(self.__socket.main, ())
            self.get_i3_workspaces()
    
        # Start bspc subprocess to get the information from bspwm
        if self.__colors['wm'] == 'bspwm':
            s = subprocess.Popen(['bspc', 'subscribe'], stdout=subprocess.PIPE)

        # Start i3status subprocess to get the status of the system
        s2 = subprocess.Popen([I3STATUS_PATH, '--config', I3STATUS_CONFIG], stdout=subprocess.PIPE)

        # Start utils subprocess for spotify, keyboard-shortcuts etc...
        s3 = subprocess.Popen([os.path.dirname(__file__) + '/utils.py'], stdout=subprocess.PIPE)

        # Register poll to act on the output of both subprocesses
        poll = select.poll()

        # Register subprocess in poll
        if self.__colors['wm'] == 'bspwm':
            poll.register(s.stdout)
        poll.register(s2.stdout)
        poll.register(s3.stdout)
        poll.register(self.__bar.stdout)

        line = ""
        utils = ""

        while self.__run:
            rlist = poll.poll()
            # Iterate through poll events
            for fd, event in rlist:
                # Get stdout of subprocesses
                ws = os.read(fd, 1024).decode('utf-8')

                # If output starts with 'SYS' there are changes in the status line
                # -> regenerate status line
                if ws.startswith('SYS'):
                    stats = ws.split(' °')[1:]
                    self.status = self.generate_status(stats)
                    self.status['spotify'] = utils

                    # If changing to battery or starting on battery, display the battery status
                    if self.current_power != self.old_power and self.current_power == 'BAT':
                        self.__show_battery = True
                    if self.current_power != self.old_power and self.current_power == 'CHR':
                        self.__show_battery = False
                    self.old_power = self.current_power

                    # Write into stdin of lemonbar
                    line = self.generate_line(self.workspaces, self.status, self.title) 
                    self.write_into_lemonbar(line)
                    continue
                elif ws.startswith('UTILS'): # Utils like spotify
                    ws = ws[5:]
                    self.__spotify = ws
                    if ws == 'None':
                        utils = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDspotify:}%{A} '
                    else:
                        if self.__show_spotify:
                            utils = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDspotify:} ' + ws[0:25] + '%{A} '
                        else:
                            utils = ' %{F' + self.__colors['status_icon_fg'] + '}%{T4}%{A:CMDspotify:}%{T-}%{A} '
                    self.status['spotify'] = utils
                    # Write into stdin of lemonbar
                    line = self.generate_line(self.workspaces, self.status, self.title) 
                    self.write_into_lemonbar(line)
                elif ws.startswith('CMD'): # Clickable icons
                    ws = ws.lstrip('CMD')
                    if ws.startswith('bat'): # Toggle battery stats
                        self.__show_battery = not self.__show_battery
                    elif ws.startswith('vol'): # Show volume stats in notification
                        notification = Notify.Notification.new("Volume", "Level: {0}".format(self.__volume), "dialog-information")
                        notification.show()
                    elif ws.startswith('wlan'): # Toggle wifi stats
                        self.__show_wlan = not self.__show_wlan
                    elif ws.startswith('eth'): # Toggle ethernet stats
                        self.__show_eth = not self.__show_eth
                    elif ws.startswith('spotify'): # Toggle spotify information
                        self.__show_spotify = not self.__show_spotify
                        if self.__spotify == 'None':
                            utils = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDspotify:}%{A} '
                        else:
                            if self.__show_spotify:
                                utils = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDspotify:}%{T4}%{T-} ' + self.__spotify[0:25] + '%{A} '
                            else:
                                utils = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDspotify:}%{A} '
                        self.status['spotify'] = utils
                    elif ws.startswith('date'):
                        if self.__calendar is None:
                            self.__calendar = subprocess.Popen(['/home/neo/.dotfiles/cal.sh'])
                        else:
                            self.__calendar.terminate()
                            self.__calendar = None
                    elif ws.startswith('ws'): # Open workspace, which is clicked
                        s = subprocess.call(['bspc', 'desktop', '-f', ws[2]])
                    elif ws.startswith('vpn'): # Show VPN in notification
                        notification = Notify.Notification.new("VPN", "Activated: {0}".format(self.__vpn), "dialog-information")
                        notification.show()

                    # Update the status, if to toggle single stats
                    self.status = self.generate_status(self.__state)
                    self.status['spotify'] = utils
                    
                    # Sum up all information in a line for lemonbar with colors and so on
                    line = self.generate_line(self.workspaces, self.status, self.title) 

                    # Write into stdin of lemonbar
                    self.write_into_lemonbar(line)
                    continue
                elif ws.startswith('WM'): # Generate workspace line
                    ws = ws.split(':')
                    layout = ws[11][1:]
                    if layout.startswith('T'):
                        layout = ''
                    else:
                        layout = ''
                    
                    # Generate workspaces from bspc output
                    self.workspaces = self.generate_workspaces(ws[1:])

                    # Get workspace root tree
                    tree = self.get_tree()
                   
                    # Get windows from root tree
                    windows = self.get_windows(tree['root'], tree['focusedNodeId']) 

                    # Check if window exist on this workspace
                    if windows != []:
                        # Check the layout of the workspace to generate the title correctly
                        if tree['layout'] == 'tiled':
                            self.title = self.get_tiled_title(windows)
                        elif tree['layout'] == 'monocle':
                            self.title = self.get_monocle_title(windows)
                    else: # Empty workspace - empty title :D
                        self.title = ""

                    # Sum up all information in a line for lemonbar with colors and so on
                    line = self.generate_line(self.workspaces, self.status, self.title) 

                    # Write into stdin of lemonbar
                    self.write_into_lemonbar(line) 

    def generate_line(self, workspaces, status, title):
        line = '%{l} ' + workspaces + ' %{B-}%{F-}'\
            + '%{B' + self.__colors['layout_bg'] + '}%{F' + self.__colors['layout_fg'] + '}%{B-}%{F-}'\
            + '%{B' + self.__colors['title_bg'] + '}%{F' + self.__colors['title_fg'] + '}' + title + ' %{B-}%{F-}'\
            + status['date'] + '%{r}' + status['vol'] + status['spotify'] + status['wlan'] + status['eth']\
            + status['vpn'] + status['bat']
        return line

    """
    @description
        Trigger on i3 workspace change and some other events to refresh the ws line.
    """
    def trigger_i3_workspaces(self, i3, event):
        if event.change in ('focus', 'init', 'empty', 'urgent', 'title'):
            self.get_i3_workspaces()

    """
    @description
        Generates the workspace and title  for i3wm.
    """
    def get_i3_workspaces(self):
        # Get workspaces
        workspaces = self.__socket.get_workspaces()
        output = ""
        for ws in workspaces:
            if ws['focused']:
                if self.__colors['focused_ws_underlined'] == 'True':
                    output += '%{B' + self.__colors['focused_ws_bg'] + '}%{F' + self.__colors['focused_ws_fg'] + '}%{T3}%{U' + self.__colors['focused_ws_fg'] + '}%{+u} %{A:CMDws' + ws['name'] + ':}' + '\uF111' + '%{A} %{-u}%{U-}%{T-}%{B-}%{F-}'
                else:
                    output += '%{B' + self.__colors['focused_ws_bg'] + '}%{F' + self.__colors['focused_ws_fg'] + '}%{T3} %{A:CMDws' + ws['name'] + ':}' + '\uF111' + '%{A} %{T-}%{B-}%{F-}'
            else:
                output += '%{B' + self.__colors['unfocused_ws_bg'] + '}%{F' + self.__colors['unfocused_ws_fg'] + '}%{T3} %{A:CMDws' + ws['name'] + ':}' + '\uF10C' + '%{A} %{T-}%{B-}%{F-}'
        self.workspaces = output

        # Get focused title
        try:
            tree = self.__socket.get_tree()
            focused = tree.find_focused()
            if focused.name:
                self.title = focused.name + ' '
                for w in workspaces:
                    if focused.name == w['name']:
                        self.title = ''
            else:
                self.title = ''
        except Exception as e:
            self.title = ''

        # Sum up all information in a line for lemonbar with colors and so on
        line = self.generate_line(self.workspaces, self.status, self.title) 

        # Write into stdin of lemonbar
        self.write_into_lemonbar(line) 

    def shutdown(self):
        print('Shut down bar')
        os.remove('/dev/shm/lemonbarpy.socket')
        self.__run = False

    """
    @description
        Write the line for lemonbar into the stdin of its subprocess and flushes it,
        so lemonbar displays the statusline
    """
    def write_into_lemonbar(self, line):
        self.__bar.stdin.write((line + '\n').encode('utf-8'))
        self.__bar.stdin.flush()

    """
    @description
        Generates the status line for lemonbar.
    """
    def generate_status(self, state):
        self.__state = state 

        date = ''
        volume = ''
        wlan = ''
        eth = ''
        battery = ''
        vpn = ''

        for s in state:
            # Volume
            if s.startswith('VOL'):
                s = s.lstrip('VOL')
                # Check if muted
                self.__volume = s
                if s.startswith('muted'):
                    volume = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDvol:}%{A}%{F' + self.__colors['status_fg'] + '} '
                else: # If not muted
                    percent = int(s[:-1])
                    # Icon to indicate the volume
                    if percent > 88:
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣿%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 88 and percent > 77: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣷%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 77 and percent > 66: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣶%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 66 and percent > 55: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣦%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 55 and percent > 44: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣤%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 44 and percent > 33: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣄%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 33 and percent > 22: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⣀%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 22 and percent > 11: 
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:} ⡀%{A}%{F' + self.__colors['status_fg'] + '} '
                    elif percent <= 11:
                        volume = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvol:}%{A}%{F' + self.__colors['status_fg'] + '} '
            # Wifi
            elif s.startswith('WLAN'):
                if self.__show_wlan: # With stats
                    if not s.lstrip('WLAN') == 'down': # Wifi down
                        wlan = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDwlan:}%{F' + self.__colors['status_fg'] + '} ' + s.lstrip('WLAN') + '%{A}  '
                    else: # Wifi connected
                        wlan = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDwlan:}%{F' + self.__colors['status_fg'] + '} ' + s.lstrip('WLAN') + '%{A}  '
                else: # Without stats
                    if not s.lstrip('WLAN') == 'down': # Wifi down
                        wlan = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDwlan:}%{A}%{F' + self.__colors['status_fg'] + '} '
                    else: # Wifi connected
                        wlan = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDwlan:}%{A}%{F' + self.__colors['status_fg'] + '} '
            # Ethernet
            elif s.startswith('ETH'):
                if self.__show_eth:  # With stats
                    if not s.lstrip('ETH') == 'down': # Eth down
                        eth = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDeth:}%{F' + self.__colors['status_fg'] + '} ' + s.lstrip('ETH') + '%{A}  '
                    else: # Eth connected
                        eth = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDeth:}%{F' + self.__colors['status_fg'] + '} ' + s.lstrip('ETH') + '%{A}  '
                else: # Without stats
                    if not s.lstrip('ETH') == 'down': # Eth down
                        eth = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDeth:}%{A}%{F' + self.__colors['status_fg'] + '} '
                    else: # Eth connected
                        eth = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDeth:}%{A}%{F' + self.__colors['status_fg'] + '} '
            # VPN
            elif s.startswith('VPN'):
                self.__vpn = s.lstrip('VPN')
                vpn_state = ''
                if s.startswith('VPNyes'):
                    interfaces = netifaces.interfaces()
                    for i in interfaces:
                        if i.startswith('ovpn'):
                            vpn_state += netifaces.ifaddresses(i)[2][0]['addr'] + ', '
                    self.__vpn = vpn_state[:-2]
                    vpn = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDvpn:}%{A}%{F' + self.__colors['status_fg'] + '} '
                else:
                    vpn = ' %{F' + self.__colors['status_icon_fg_muted'] + '}%{A:CMDvpn:}%{A}%{F' + self.__colors['status_fg'] + '} '
            # Battery
            elif s.startswith('BATT'):
                s = s[4:]
                # If discharging, display the battery status
                self.current_power = re.sub(r'([BATUNKFLCHR]*)\s.*', r'\1', s)

                # If battery is not charging
                if self.__show_battery: # Display battery stats
                    if s.startswith('BAT') or s.startswith('UNK') or s.startswith('FLL'):
                        on_battery = False
                        if s.startswith('BAT'):
                            on_battery = True
                        percent = int(s.split(' ')[1].split(',')[0])
                        s = s.lstrip('BAT ')
                        s = s.lstrip('UNK ')
                        s = s.lstrip('FULL ')
                        #  Change icon related to the actual battery load
                        if percent > 80:
                            battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + '%{A}  '
                        elif percent <= 80 and percent > 50:
                            battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + '%{A}  '
                        elif percent <= 50 and percent > 30:
                            battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + '%{A}  '
                        elif percent <= 30:
                            battery = ' %{F' + self.__colors['status_alarm_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_alarm_fg'] + '} ' + s + '%{A}  '

                        # Show watt usage when in battery mode
                        if on_battery:
                            with open('/sys/class/power_supply/BAT0/power_now', 'r') as fp:
                                watt = fp.read()
                                watt = re.sub('\.', ',', str(int(watt.rstrip('\n')) / 1000000)[0:4] + 'W')
                            #  Change icon related to the actual battery load
                            if percent > 80:
                                battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + ' ' + watt + '%{A}  '
                            elif percent <= 80 and percent > 50:
                                battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + ' ' + watt + '%{A}  '
                            elif percent <= 50 and percent > 30:
                                battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + ' ' + watt + '%{A}  '
                            elif percent <= 30:
                                battery = ' %{F' + self.__colors['status_alarm_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_alarm_fg'] + '} ' + s + ' ' + watt + '%{A}  '
                    elif s.startswith('CHR'): # If it charges, change icon
                        s = s.lstrip('CHR ')
                        battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{F' + self.__colors['status_fg'] + '} ' + s + '%{A}  '
                else: # Hide battery stats
                    if s.startswith('BAT') or s.startswith('UNK') or s.startswith('FLL'):
                        percent = int(s.split(' ')[1].split(',')[0])
                        s = s.lstrip('BAT ')
                        s = s.lstrip('UNK ')
                        s = s.lstrip('FULL ')
                        #  Change icon related to the actual battery load
                        if percent > 80:
                            battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{A}%{F' + self.__colors['status_fg'] + '} '
                        elif percent <= 80 and percent > 50:
                            battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{A}%{F' + self.__colors['status_fg'] + '} '
                        elif percent <= 50 and percent > 30:
                            battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{A}%{F' + self.__colors['status_fg'] + '} '
                        elif percent <= 30:
                            battery = ' %{F' + self.__colors['status_alarm_fg'] + '}%{A:CMDbat:}%{A}%{F' + self.__colors['status_alarm_fg'] + '} '
                    elif s.startswith('CHR'): # If it charges, change icon
                        s = s.lstrip('CHR ')
                        battery = ' %{F' + self.__colors['status_icon_fg'] + '}%{A:CMDbat:}%{A}%{F' + self.__colors['status_fg'] + '} '
            # Date
            elif s.startswith('DATE'):
                date = '%{c}%{F' + self.__colors['status_fg'] + '}%{A:CMDdate:} ' + s.lstrip('DATE')[:-1].split(' ')[1] + '%{A} '
        status = {}
        status['date'] = date
        status['vol'] = volume
        status['wlan'] = wlan
        status['eth'] = eth
        status['bat'] = battery
        status['vpn'] = vpn
        return status

    """
    @description
        Generate the status line for the workspaces.
    """
    def generate_workspaces(self, ws):
        output = ""
        # Go over workspaces
        for w in ws:
            if w == ws[10]:
                break
            if w[0] == 'o':
                output += '%{B' + self.__colors['unfocused_ws_bg'] + '}%{F' + self.__colors['unfocused_ws_fg'] + '}%{T3} %{A:CMDws' + w[1] + ':}' + '\uF111' + '%{A} %{T-}%{B-}%{F-}'
            elif w[0] == 'O':
                if self.__colors['focused_ws_underlined'] == 'True':
                    output += '%{B' + self.__colors['focused_ws_bg'] + '}%{F' + self.__colors['focused_ws_fg'] + '}%{T3}%{U' + self.__colors['focused_ws_fg'] + '}%{+u} %{A:CMDws' + w[1] + ':}' + '\uF111' + '%{A} %{-u}%{U-}%{T-}%{B-}%{F-}'
                else:
                    output += '%{B' + self.__colors['focused_ws_bg'] + '}%{F' + self.__colors['focused_ws_fg'] + '}%{T3} %{A:CMDws' + w[1] + ':}' + '\uF111' + '%{A} %{T-}%{B-}%{F-}'
            elif w[0] == 'f':
                output += '%{B' + self.__colors['unfocused_ws_bg'] + '}%{F' + self.__colors['unfocused_ws_fg'] + '}%{T3} %{A:CMDws' + w[1] + ':}' + '\uF10C' + '%{A} %{T-}%{B-}%{F-}'
            elif w[0] == 'F':
                if self.__colors['focused_ws_underlined'] == 'True':
                    output += '%{B' + self.__colors['focused_ws_bg'] + '}%{F' + self.__colors['focused_ws_fg'] + '}%{T3}%{U' + self.__colors['focused_ws_fg'] + '}%{+u} %{A:CMDws' + w[1] + ':}' + '\uF10C' + '%{A} %{-u}%{T-}%{B-}%{F-}'
                else:
                    output += '%{B' + self.__colors['focused_ws_bg'] + '}%{F' + self.__colors['focused_ws_fg'] + '}%{T3} %{A:CMDws' + w[1] + ':}' + '\uF10C' + '%{A} %{T-}%{B-}%{F-}'
        return output

    """
    @description
        Get title line for the focused window.
        Returns a string in lemonbar syntax.
    """
    def get_tiled_title(self, windows):
        for window in windows:
            if window['focus']:
                return '%{B' + self.__colors['title_bg'] + '}%{F' + self.__colors['title_fg'] + '} ' + window['title'][:40] + ' %{B-}%{F-}'
        return ""

    """
    @descpription
        Get title line for every window and underline the focused one.
        Returns a string in lemonbar syntax.
    """
    def get_monocle_title(self, windows):
        output = ""
        
        if len(windows) <= 3:
            for window in windows:
                # If window is focused, underline the title
                if window['focus']:
                    output += '%{B' + self.__colors['title_monocle_bg'] + '}%{F' + self.__colors['title_monocle_fg'] + '}%{U' + self.__colors['title_monocle_fg'] + '}%{+u} ' + window['title'][:40] + ' %{-u}%{B-}%{F-}'
                else:
                    output += '%{B' + self.__colors['title_monocle_bg'] + '}%{F' + self.__colors['title_monocle_fg'] + '} ' + window['title'][:40] + ' %{B-}%{F-}'
        else:
            for i in range(len(windows)):
                if windows[i]['focus']:
                    output += ' %{B' + self.__colors['title_monocle_bg'] + '}%{F' + self.__colors['title_monocle_fg'] + '} ' + windows[(i - 1) % len(windows)]['title'][:40] + ' %{B-}%{F-}'
                    output += '%{B' + self.__colors['title_monocle_bg'] + '}%{F' + self.__colors['title_monocle_fg'] + '}%{U' + self.__colors['title_monocle_fg'] + '}%{+u} ' + windows[i]['title'][:40] + ' %{-u}%{B-}%{F-}'
                    output += '%{B' + self.__colors['title_monocle_bg'] + '}%{F' + self.__colors['title_monocle_fg'] + '} ' + windows[(i + 1) % len(windows)]['title'][:40] + '  %{B-}%{F-}'
            pass
        return output[:-3]

    """
    @description
        Get the full title for a window id.
    """
    def get_title(self, id):
        s = subprocess.Popen(['bspc', 'query', '-N', '-n', str(id)], stdout=subprocess.PIPE)
        r = s.communicate()[0].decode('utf-8')
        
        s = subprocess.Popen(['xtitle', str(r).rstrip('\n')], stdout=subprocess.PIPE)
        title = s.communicate()[0].decode('utf-8').rstrip('\n')
        return title

    """
    @description
        Get an array, which contains name, focus and window id of every node.
    """
    def get_windows(self, tree, focused_id):
        windows = []
        
        # Save focused id because you dont get the information later
        if tree is not None:
            focus = focused_id == tree['id']
        else:
            return []
            
        # Check if node is a leaf(has no child nodes)
        if tree['firstChild'] is None and tree['secondChild'] is None:
            # Return name, focus and window title of the node
            return [{'name':tree['client']['instanceName'], 'focus':focus, 'title':self.get_title(tree['id'])}]
        else:
            # Check the other nodes recursively through the window root tree
            deeper_tree = self.get_windows(tree['firstChild'], focused_id)
            if tree['secondChild'] is not None:
                deeper_tree.extend(self.get_windows(tree['secondChild'], focused_id))

            for leaf in deeper_tree:
                windows.append(leaf)
        
            if tree['client'] is not None:
                # Return name, focus and title of the node
                windows.append({'name':tree['client']['instanceName'], 'focus':focus, 'title':self.get_title(tree['id'])})

            # Return nodes after iterating through the tree
            return windows


def main():
    b = BSPWM(None)
    b.get_workspaces()
    pass


if __name__ == '__main__':
    main()
