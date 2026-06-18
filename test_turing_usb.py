import usb.core
import usb.util
import time
import struct
import platform
import sys
from Crypto.Cipher import DES

def encrypt_with_des(key: bytes, data: bytes) -> bytes:
    cipher = DES.new(key, DES.MODE_CBC, key)
    padded_len = (len(data) + 7) // 8 * 8
    padded_data = data.ljust(padded_len, b'\x00')
    return cipher.encrypt(padded_data)

def encrypt_command_packet(data: bytearray) -> bytearray:
    des_key = b'slv3tuzx'
    encrypted = encrypt_with_des(des_key, data)
    final_packet = bytearray(512)
    final_packet[:len(encrypted)] = encrypted
    final_packet[510] = 161
    final_packet[511] = 26
    return final_packet

def build_command_packet_header(a0: int) -> bytearray:
    packet = bytearray(500)
    packet[0] = a0
    packet[2] = 0x1A
    packet[3] = 0x6D
    timestamp = int((time.time() - time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))) * 1000)
    packet[4:8] = struct.pack('<I', timestamp)
    return packet

def find_usb_device():
    dev = usb.core.find(idVendor=0x0483, idProduct=0x0065)
    if dev is None:
        raise ValueError("USB device not found")
    
    if platform.system() == "Linux":
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except usb.core.USBError as e:
            print("Warning: detach_kernel_driver failed:", e)

    try:
        dev.set_configuration()
    except usb.core.USBError as e:
        print("Warning: set_configuration() failed:", e)

    return dev

def read_flush(ep_in, max_attempts=5):
    for _ in range(max_attempts):
        try:
            ep_in.read(512, timeout=100)
        except usb.core.USBError as e:
            if e.errno == 110 or e.args[0] == 'Operation timed out':
                break
            else:
                break

def write_to_device(dev, data, timeout=2000):
    cfg = dev.get_active_configuration()
    intf = usb.util.find_descriptor(cfg, bInterfaceNumber=0)
    if intf is None:
        raise RuntimeError("USB interface 0 not found")
    ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(
        e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
    ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(
        e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    assert ep_out is not None and ep_in is not None, "Could not find USB endpoints"

    try:
        ep_out.write(data, timeout)
    except usb.core.USBError as e:
        print("USB write error:", e)
        return None

    try:
        response = ep_in.read(512, timeout)
        read_flush(ep_in)
        return bytes(response)
    except usb.core.USBError as e:
        print("USB read error:", e)
        return None

def send_sync_command(dev):
    print("Sending Sync Command (ID 10)...")
    cmd_packet = build_command_packet_header(10)
    res = write_to_device(dev, encrypt_command_packet(cmd_packet))
    print("Response:", res)
    return res

if __name__ == '__main__':
    try:
        dev = find_usb_device()
        print("Device found and configuration set.")
        res = send_sync_command(dev)
        if res:
            print("Successfully communicated with device!")
        else:
            print("Communicated, but response was empty or failed.")
    except Exception as e:
        print("Error:", e)
