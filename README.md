# GWM Vehicle Config Editor
## Description
Simple tool to edit `/data/vendor/vehicle/info/VehicleConfig.bin` in HUT to enable advanced features without an OBD2 scanner like ThinkDiag.
Use `adb root` to access configuration file.
## Requirements
Python 3.2 or newer.
## Usage
```
vce [--map <path-to-map-file>] [--type <config-type|binary,text>] [--src <path-to-source-config-file|VehicleConfig.bin,VehicleConfig.txt>] [--dst <path-to-source-config-file|NewVehicleConfig.bin,NewVehicleConfig.txt>] property1:bitstring1...propertyN=valueN
```
## Configuration map
|Project code|Vehicle|Model Year|Region|
|---------|----------|----------|----------|
|0x36 (54)|Haval Jolion|2021-2023|China|
|0x44 (68)|Haval Jolion|2021-2023|Russia|
|0x82 (130)|Haval Jolion|2024-2025|China|
|0x8F (143)|Haval Jolion|2024-2025|Russia|
