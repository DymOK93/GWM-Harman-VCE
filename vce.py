
import argparse
import json
import re

#
# Project code property: 'ro.vehicle.config.AAA'
#
kProjectCodeProperty = 'AAA'

#
# Calculates CRC8
# @param[in] data: Binary data without CRC byte
# @return CRC value
#
def calcCrc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc ^= 0x8380
            crc *= 2
    return (crc >> 8) & 0xFFFFFF

#
# Reads binary files
# @param[in] path: File path
#
def readConfig(path: str) -> bytearray:
    with open(path, 'rb') as cfg:
        return bytearray(cfg.read())
    
#
# Writes binary files
# @param[in] path: File path
# @param[in] data: Binary data
#
def writeConfig(path: str, data: bytes):
    with open(path, 'wb') as cfg:
        cfg.write(data)

#
# Reads JSON in UTF-8 encoding
# @param[in] path: File path
#
def readMap(path: str):
    with open(path, 'r', encoding = 'utf-8') as map:
        return json.load(map)
    
#
# Extracts position table from JSON
# @param[in] map: JSON config
#
def getPositionTable(map) -> str:
    return map['ro.vehicle.config']

#
# Config entry position
#
class Position:
    byte_idx = 0
    high_bit = 0
    low_bit = 0

    def _is_valid_bit_pos(self, pos: int) -> bool:
        return 0 <= pos <= 7

    #
    # @param[in] pos: Position string in format "[byte_idx][high_bit:low_bit]"
    #
    def __init__(self, pos: str):
        match = re.match(r"\[(\d+)\]\[(\d+):(\d+)\]", pos)
        if not match:
            raise ValueError(f"Invalid position format: {pos}")
        
        byte_idx, high_bit, low_bit = map(int, match.groups())
        if not self._is_valid_bit_pos(high_bit):
            raise OverflowError(f"High bit {hb} should be in range [0...7]")

        if not self._is_valid_bit_pos(low_bit):
            raise OverflowError(f"Low bit {low_bit} should be in range [0...7]")
        
        if low_bit > high_bit:
            raise OverflowError(f"Low bit {low_bit} should be less than high bit {high_bit}")
        
        self.byte_idx = byte_idx
        self.high_bit = high_bit
        self.low_bit = low_bit
#
# Reads bits at a given position
# @param[in] data: Configuration bytes
# @return Little-endian bitstring 
#
def readBits(data: bytes, pos: Position) -> str:
    bitstr = format(data[pos.byte_idx], '08b')
    return bitstr[::-1][pos.low_bit:pos.high_bit + 1][::-1]

#
# Writes bits at a given position
# @param[in] data: Configuration bytes
# @param[in] pos: Position
# @param[in] value: Little-endian bitstring
#
def writeBits(data: bytearray, pos: Position, value: str):
    value_len = len(value)
    expected_len = pos.high_bit - pos.low_bit + 1
    if value_len != expected_len:
        raise OverflowError(f'Bistring length {value_len} is not equal to expected {expected_len}')
    
    bitlist = list(format(data[pos.byte_idx], '08b'))[::-1]
    bitlist[pos.low_bit:pos.high_bit + 1] = list(value)[::-1]
    data[pos.byte_idx] = int(''.join(bitlist[::-1]), 2)

#
# Validates config size and project code against map
# @param[in] data: Configuration bytes
# @param[in] map: JSON config
#
def validateConfig(data: bytes, map) -> None:
    data_len = len(data)
    if data_len == 0 or data_len != map['size']:
        raise ValueError(f'Config size should be {data_len}')
    
    table = getPositionTable(map)
    aaa = table['AAA']
    expected_project_code = map['project_code']
    bstr = readBits(data, Position(aaa))
    actual_project_code = int(bstr, 2)
    if expected_project_code != actual_project_code:
        raise ValueError(f"Unsupported project code: expected {expected_project_code}, got {actual_project_code}")
    
    for property, pos in table.items():
        position = Position(pos)
        if position.byte_idx >= data_len - 1:  # Last byte is CRC
            raise OverflowError(f'Property {property} has invalid index {position.byte_idx}')

#
# Do processing and enjoy
#
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', dest = 'map', type = str, default = "map.json", help = "path to JSON file with mapping of properties to config bits")
    parser.add_argument('--src', dest = 'src', type = str, default = "VehicleConfig.bin", help = "path to source config binary file")
    parser.add_argument('--dst', dest = 'dst', type = str, default = "NewVehicleConfig.bin", help = "path to destination config binary file")
    parser.add_argument('props', metavar = 'PROPERTY:BITSTRING', type = str, nargs = '+', help = "property:bitstring pairs")
    args = parser.parse_args()
   
    print(f'Read property map from {args.map}')
    map = readMap(args.map)

    print(f'Read config from {args.src}')
    data = readConfig(args.src)
    validateConfig(data, map)
    updated = False

    for prop_bitstr in args.props:
        property = prop_bitstr.split(':')[0]
        bitstr = prop_bitstr.split(':')[1]
        if property == kProjectCodeProperty:
            raise ValueError(f'Project code change is not supported')

        position = getPositionTable(map).get(property)
        if position is None:
            raise KeyError(f"Property '{property}' not found in map")

        writeBits(data, Position(position), bitstr)
        updated = True

    if updated:
        print(f'Save updated config to {args.dst}')
        data[-1] = calcCrc8(data[:-1])
        writeConfig(args.dst, data)

#
# Launch main
#
if __name__ == "__main__":
    main()






