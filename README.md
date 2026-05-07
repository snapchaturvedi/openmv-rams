# OpenMV Firmware for remote animal microchip scanner (RAMS)

## Prithul Chaturvedi 

### Instructions
Windows Subsystem Linux (WSL) Ubuntu-20.04 was used to do everything on my computer itself.
Make a folder to work in. Don't go out of this folder unnecessarily

```
sudo mkdir OPENMVFIRMWARE
```

Basic things before you get started
```
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install git build-essential
```

Deep clone the OpenMV git repo that I have forked
```
git clone --recursive https://github.com/snapchaturvedi/openmv-rams.git
cd openmv-rams
```

Alternatively, you can shallow clone the OpenMV git repo. Avoid this if possible (Kwabena Agyeman suggested)
```
git clone --depth=1 https://github.com/snapchaturvedi/openmv-rams.git
cd openmv-rams
git submodule update --init --depth=1 --no-sincd ..gle-branch`
git -C lib/micropython/ submodule update --init --depth=1
```

Install OpenMV's SDK (software development kit)
```
make sdk
```
Add your custom code to scripts/libraries at this step
All the files go here including helper scripts
Script here will override any program of the same name saved on flash/SD-card

Go to `/openmv/boards/ARDUINO_PORTENTA_H7/manifest.py` and add the following line for all your programs somewhere:

```{py}
# <PC 20260429> Frozen main program and utility modules for bait dispenser
freeze ("$(OMV_LIB_DIR)/", "main.py")
freeze ("$(OMV_LIB_DIR)/", "ds1307.py")
freeze ("$(OMV_LIB_DIR)/", "wl134.py")
```


<PC 20260501> Freeze your model (devil.tflite) also
Place the model in /openmv/lib/models
Edit openmv/boards/ARDUINO_PORTENTA_H7/romfs_config.json and add the following in the same way :
```{json}
    {
      "type": "tflite",
      "path": "{TOP}/lib/models/devil.tflite",
      "alignment": 16,
      "optimize": "Performance"
    }
```
--------------------------------------------

Build firmware with these lines
```
make -j$(nproc) -C lib/micropython/mpy-cross   # Builds MicroPython mpy cross-compiler
make -j$(nproc) TARGET=ARDUINO_PORTENTA_H7     # Builds the OpenMV firmware
```
The resulting firmware.bin will be located in the build/bin/ folder

Flash to Device:
1. Connect your OpenMV Cam via USB
2. Open the OpenMV IDE
3. Go to Tools > Run Bootloader
4. Select your custom firmware.bin and follow the prompts to flash the device. Erase internal FAT and reset ROMFS file systems.


To rebuild firmware, make changes and run:
```
make -j$(nproc) -C lib/micropython/mpy-cross && make -j$(nproc) TARGET=ARDUINO_PORTENTA_H7
```

Might have to edit ROMFS and add devil.tflite. Do this after loading custom firmware.
