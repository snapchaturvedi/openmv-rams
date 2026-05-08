# OpenMV Firmware for remote animal microchip scanner (RAMS)

## Prithul Chaturvedi, William M. Connelly, Soyeon Caren Han,  Andrew S. Flies

This guide covers installing a development environment and building the OpenMV firmware for RAMS. This repo is forked from https://github.com/openmv.

Key things to keep in mind during development:

1. Ensure that each bash command runs without errors or warnings.
2. Ensure that your OpenMV IDE is up to date. Find the latest version [here](https://openmv.io/pages/download?srsltid=AfmBOoqA1WcHYXcm1siVzhMTBT8fiq8zR1BQmfoQOZwbRtzLrbuJTFnK).
3. Confirm which camera you're using on your device.
    - We recommend using HM0360 VGA camera for RAMS. Some Portenta Vision Shields come with this camera; however they have infrared filters on. HM0360 NoIR can be procured by directly contacting Arducam.
    - If you're using HM01B0 QVGA camera, you must update the `openmc-rams/scripts/libraries/main.py` and change `camera.framesize(csi.VGA)` to `camera.framesize(csi.QVGA)`.

### Instructions to build firmware
Windows Subsystem Linux (WSL) Ubuntu-20.04 was used to do everything on my computer itself.

1. Make a folder to work in. Don't go out of this folder unnecessarily:

```bash
sudo mkdir OPENMVFIRMWARE
```

2. Basic things before you get started:

```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install git build-essential
```

3. Deep clone the OpenMV git repo that I have forked. This repo has all the necessary files for RAMS:

```bash
git clone --recursive https://github.com/snapchaturvedi/openmv-rams.git
cd openmv-rams
```

Alternatively, you can shallow clone the OpenMV git repo. Avoid this if possible (Kwabena Agyeman suggested):

```bash
git clone --depth=1 https://github.com/snapchaturvedi/openmv-rams.git
cd openmv-rams
git submodule update --init --depth=1 --no-sincd ..gle-branch`
git -C lib/micropython/ submodule update --init --depth=1
```

4. Install OpenMV's SDK (software development kit):

```bash
make sdk
```

5. You're now ready to build the firmware with these lines:

```bash
make -j$(nproc) -C lib/micropython/mpy-cross   # Builds MicroPython mpy cross-compiler
make -j$(nproc) TARGET=ARDUINO_PORTENTA_H7     # Builds the OpenMV firmware
```

The resulting `firmware.bin` along with other build artifacts will be located in the `build/bin` folder.


### Flash firmware to Device:
1. Connect your ArduinoPro H7 Portenta + Vision Shield (LoRa) via USB. Ensure the device has an SD card (at least 32 GB recommended).
2. Open the OpenMV IDE.
3. Go to Tools > Run Bootloader.
4. Select your custom firmware.bin and follow the prompts to flash the device. Erase internal FAT  file systems and reset [ROMFS](https://openmv.io/blogs/news/romfs-support-is-here?srsltid=AfmBOoqvSMMwU7kR9aTYmZasXN4lhuYp6WmUBPDT4ReHv1igfYjwsyJc).

You might have to edit ROMFS and add the image classificaiton model `devil.tflite`. Do this after loading custom firmware.

### Rebuild firmware
To rebuild firmware, make your changes and run the following lines. Only updated files will change upon rebuild.

```bash
make -j$(nproc) -C lib/micropython/mpy-cross && make -j$(nproc) TARGET=ARDUINO_PORTENTA_H7
```

