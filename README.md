<p align="center">
  <img src="DualsenseChordKeeper.png" alt="DualSense Chord Keeper Logo" width="200">
</p>

# DualSense Chord Keeper

DualSense Chord Keeper is a tool created out of frustration. I constantly would forget what device I had connected to what button and I decided to try to do something about it. This is AI code, all of it. I wanted to also use this as a way to learn and better understand how to code, so in the future I'd like to do a whole rewrite with properly checked over code. Use at your own risk, I haven't had any issues but who knows.

---

## Features

### Real-time Notifications
With the press of a button you too can be reminded what the hell you bound your PC to!

![Placeholder: Notification Overlay]

### Configuration
Though a little odd, most of the features you need to customize the position and look. The horizontal and vertical sliders should be allow you to fix the position
of the notification pretty decently.

![Placeholder: Configuration Menu]

### System Tray Integration
Runs quietly in the background. Access settings, toggle features, or exit the application directly from the Windows system tray.

---

## Getting Started

### Prerequisites
- Windows 10 or 11
- Sony DualSense Wireless Controller (connected via USB or Bluetooth)

### Installation
1. Download the latest release from the [Releases](https://github.com/Jonahlahona/Dualsense-Chord-Keeper/releases) page.
2. Extract the contents to a folder of your choice.
3. Run `DualSenseChordKeeper.exe`.

---

## Usage
1. Open the configuration interface from the system tray icon.
2. Define your desired chords by selecting the primary buttons and the resulting action.
3. Save your settings and start using your controller to trigger actions.

---

## Development

If you wish to build from source:

1. Clone the repository:
   ```bash
   git clone https://github.com/Jonahlahona/Dualsense-Chord-Keeper.git
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python src/main.py
   ```

---

## License
Distributed under the MIT License. See `LICENSE` for more information.
