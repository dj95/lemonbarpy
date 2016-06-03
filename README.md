# lemonbarpy 

Easy to use lemonbar parser.


### Features

- Lightweight status line for bspwm with lemonbar and i3status
- Toggle status elements to icon or icon and text with left mouse button
- Select workspace with mouse click
- Transparency


### Screenshots

![shot1](./img/shot1.png)
![shot2](./img/shot2.png)


### Requirements

- Python 3
- my [i3status](https://github.com/dj95/i3status) fork
- Lemonbar with XFT-Patch
- libnotify
- python-gobject
- BSPWM(>= 0.9.1)
- Fonts:
  - Ionicons
  - Serif
  - Terminesspowerline
  - Icons


### Installation

- Just clone this repository to any direction.
- Add this line to your `~/.config/bspwm/bspwmrc`, where $PATH is the directory from the step above

```
./$PATH/src/lemonbarpy.py &
```
- Change the CONFIG_FILE-constant in `src/lemonbar.py` to your config-file-path
- Change the I3STATUS_PATH in `src/bspwm.py` to your i3status-installation
- Change the I3STATUS_CONFIG in `src/bspwm.py` to your i3status-config-path


### License

(c) 2016 Daniel Jankowski

This project is licensed under the MIT License.
Check out [LICENSE](./LICENSE) for more information.
