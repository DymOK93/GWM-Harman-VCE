import argparse
import json
import re
from abc import ABC, abstractmethod

#
# Project code property: 'ro.vehicle.config.AAA'
#
kProjectCodeProperty = 'AAA'

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

    def _isValidBitPos(self, pos: int) -> bool:
        return 0 <= pos <= 7

    #
    # @param[in] pos: Position string in format "[byte_idx][high_bit:low_bit]"
    #
    def __init__(self, pos: str):
        match = re.match(r'\[(\d+)\]\[(\d+):(\d+)\]', pos)
        if not match:
            raise ValueError(f'Invalid position format: {pos}')
        
        byte_idx, high_bit, low_bit = map(int, match.groups())
        if not self._isValidBitPos(high_bit):
            raise OverflowError(f'High bit {high_bit} should be in range [0...7]')

        if not self._isValidBitPos(low_bit):
            raise OverflowError(f'Low bit {low_bit} should be in range [0...7]')
        
        if low_bit > high_bit:
            raise OverflowError(f'Low bit {low_bit} should be less than high bit {high_bit}')
        
        self.byte_idx = byte_idx
        self.high_bit = high_bit
        self.low_bit = low_bit
#
# Reads bits at a given position
# @param[in] data: Configuration bytes
# @param[in] pos: Position
# @return Little-endian bitstring 
#
def readBits(data: bytes, pos: Position) -> str:
    bitstr = format(data[pos.byte_idx], '08b')
    return bitstr[8 - pos.high_bit - 1:8 - pos.low_bit]

#
# Reads number at a given position
# @param[in] data: Configuration bytes
# @param[in] pos: Position
# @return Number
#
def readNumber(data: bytes, pos: Position) -> int:
    return int(readBits(data, pos), 2)

#
# Writes bits at a given position
# @param[in,out] data: Configuration bytes
# @param[in] pos: Position
# @param[in] value: Little-endian bitstring
#
def writeBits(data: bytearray, pos: Position, value: str) -> str:
    value_len = len(value)
    expected_len = pos.high_bit - pos.low_bit + 1
    if value_len != expected_len:
        raise OverflowError(f'Bistring length {value_len} is not equal to expected {expected_len}')
    
    bitstr = format(data[pos.byte_idx], '08b')
    bitlist = list(bitstr)
    bitlist[8 - pos.high_bit - 1:8 - pos.low_bit] = list(value)
    data[pos.byte_idx] = int(''.join(bitlist), 2)
    return bitstr[8 - pos.high_bit - 1:8 - pos.low_bit]

#
# Writes number at a given position
# @remark Value is converted to a bit string of required length (padded with leading zeros)
# @param[in,out] data: Configuration bytes
# @param[in] pos: Position
# @param[in] value: Number
#
def writeNumber(data: bytearray, pos: Position, value: int) -> int:
    bitstr = format(value, 'b')
    actual_len = len(bitstr)
    expected_len = pos.high_bit - pos.low_bit + 1

    if actual_len > expected_len:
        raise OverflowError(f'Value {value} is too large')
    
    if actual_len < expected_len:
        bitstr = '0' * (expected_len - actual_len) + bitstr 
    
    old_bitstr = writeBits(data, pos, bitstr)
    return int(old_bitstr, 2)

#
# Validates config size and project code against map
# @param[in] data: Configuration bytes
# @param[in] map: JSON config
#
def validateConfig(data: bytes, map) -> None:
    config_size = len(data)
    expected_size = map['config_size'] # Size without CRC byte
    if config_size != expected_size:  
        raise ValueError(f'Config size {config_size} should be {expected_size}')
    
    table = getPositionTable(map)
    project_code = readNumber(data, Position(table['AAA']))
    if not project_code in map['project_code']:
        raise ValueError(f'Unsupported project code {project_code}')
    
    for property, pos in table.items():
        position = Position(pos)
        if position.byte_idx >= config_size:
            raise OverflowError(f'Property {property} has invalid index {position.byte_idx}')
        
#
# Property name and value
#
class Property:
    @staticmethod
    def _splitProps(sep: str, props: str):
        split = props.split(sep)
        if len(split) < 2:
            return None
        return split
    
    @staticmethod
    def _extractBitstr(s: str) -> str:
        if len(s) == 0 or not all(c in '01' for c in s):
            raise ValueError(f'Bitstring {s} should contain only 0 and 1')
        return s
    
    @staticmethod
    def _extractNumber(s: str) -> int:
        n = int(s, 0)         # Select base automatically
        if n < 0 or n > 255:  # Should fit in a byte
            raise ValueError(f'Number {n} should be positive and less than 255')
        return n

    def __init__(self, props: str):
        split = Property._splitProps(':', props)
        if not split is None:
            self.name = split[0]
            self.value = Property._extractBitstr(split[1])
            return
        
        split = Property._splitProps('=', props)
        if not split is None:
            self.name = split[0]
            self.value = Property._extractNumber(split[1])
            return

        raise ValueError(f'Argument {props} should be in format PROPERTY:BITSTRING or PROPERTY=DECVALUE or PROPERTY=HEXVALUE')
    
    def apply(self, data: bytearray, pos: Position) -> None:
        value = self.value

        if isinstance(value, str):
            old_value = writeBits(data, pos, value)
        else: # value should be int
            old_value = writeNumber(data, pos, value)
        
        print(f'Update property {self.name}: {old_value} -> {value}')
    
#
# Abstract vehicle configuration
#
class ISerializer(ABC):
    def _openFile(self, path: str, writeable: bool):
        mode = ['r', 'w'][writeable] + ['', 'b'][self._isBinary()]
        return open(path, mode)

    def read(self, path: str) -> bytes:
        with self._openFile(path, False) as cfg:
            return self._decode(cfg.read())

    def write(self, path: str, data: bytes) -> None:
        with self._openFile(path, True) as cfg:
            cfg.write(self._encode(data))

    @abstractmethod
    def _isBinary(self) -> bool:
        pass

    @abstractmethod
    def _decode(self, data) -> bytes:
        pass

    @abstractmethod
    def _encode(self, data: bytes):
        pass

#
# Binary configuration serializer (for VehicleConfig.bin with CRC in last byte)
#
class BinarySerializer(ISerializer): 
    @staticmethod
    def _calcCrc8(data: bytes):
        crc = 0
        for b in data:
            crc ^= b << 8
            for _ in range(8):
                if (crc & 0x8000) != 0:
                    crc ^= 0x8380
                crc *= 2
        return (crc >> 8) & 0xFFFFFF
    
    def _isBinary(self) -> bool:
        return True

    def _decode(self, data: bytes) -> bytes:
        return data[:-1]  # config without last byte

    def _encode(self, data: bytes) -> bytes:
        return data + bytes([BinarySerializer._calcCrc8(data)])

#
# Text configuration serializer (for VehicleConfig.txt without CRC)
#
class TextSerializer(ISerializer): 
    def _isBinary(self) -> bool:
        return False

    def _decode(self, data: str) -> bytes:
        return bytes.fromhex(data)

    def _encode(self, data: bytes) -> str:
        return data.hex()
#
# Creates configuration serializer 
#
def createSerializer(type: str):
    if type == 'binary':
        return BinarySerializer()
    
    if type == 'text':
        return TextSerializer()
    
    raise ValueError(f'Unknown config type {type}')

#
# Creates parsers for 'type'-dependent arguments
#
def getFilePaths(binary: bool, src, dst) -> tuple:
    extensions = ['.txt', '.bin']

    if src is None:
        src = 'VehicleConfig' + extensions[binary]

    if dst is None:
        dst = 'NewVehicleConfig' + extensions[binary]  

    return (src, dst)

#
# Does processing
#
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--map', dest = 'map', type = str, default = 'map.json', help = 'path to JSON file with mapping of properties to config bits')
    parser.add_argument('--type', dest = 'type', type = str, default = 'binary', help = 'config file type: binary or text')
    parser.add_argument('--src', dest = 'src', type = str, help = 'path to source config file')
    parser.add_argument('--dst', dest = 'dst', type = str, help = 'path to destination config file')
    parser.add_argument('props', type = str, nargs = '+', help = 'property:bitstring or property=value pairs')
    args = parser.parse_args()
   
    print(f'Read property map from {args.map}')
    map = readMap(args.map)
    
    serializer = createSerializer(args.type)
    src, dst = getFilePaths(args.type == 'binary', args.src, args.dst)

    print(f'Read config from {src}')
    data = bytearray(serializer.read(src))
    validateConfig(data, map)
    updated = False

    for property in [Property(p) for p in args.props]:
        name = property.name
        if name == kProjectCodeProperty:
            raise ValueError(f'Project code change is not supported')

        position = getPositionTable(map).get(name)
        if position is None:
            raise KeyError(f"Property '{name}' not found in map")
        
        property.apply(data, Position(position))
        updated = True

    if updated:
        print(f'Save updated config to {dst}')
        serializer.write(dst, data)

#
# Launches main
#
if __name__ == "__main__":
    main()
