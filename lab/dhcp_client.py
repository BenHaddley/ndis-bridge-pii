#!/usr/bin/env python3
"""Small DHCP DORA probe for the isolated lab, not a production lease manager.

Requests one lease and prints it as JSON. Does not configure interfaces or renew.
Wire format: RFC 2131; option encoding: RFC 2132.
"""
import argparse
import fcntl
import ipaddress
import json
import secrets
import socket
import struct
import time

COOKIE = b'\x63\x82\x53\x63'
HEADER = struct.Struct('!BBBBIHH4s4s4s4s16s64s128s')


def options(data):
    result = {}
    pos = 0
    while pos < len(data):
        code = data[pos]
        pos += 1
        if code == 255:
            return result
        if code == 0:
            continue
        if pos >= len(data):
            raise ValueError('truncated DHCP option length')
        size = data[pos]
        pos += 1
        if pos + size > len(data):
            raise ValueError('truncated DHCP option value')
        result[code] = data[pos:pos + size]
        pos += size
    return result


def packet(xid, mac, kind, requested=None, server=None):
    zero = b'\0' * 4
    header = HEADER.pack(1, 1, 6, 0, xid, 0, 0x8000,
                         zero, zero, zero, zero, mac.ljust(16, b'\0'),
                         b'\0' * 64, b'\0' * 128)
    opts = bytes([53, 1, kind, 61, 7, 1]) + mac + bytes([55, 4, 1, 3, 51, 54])
    if requested is not None:
        opts += bytes([50, 4]) + requested
    if server is not None:
        opts += bytes([54, 4]) + server
    return (header + COOKIE + opts + b'\xff').ljust(300, b'\0')


def reply(data, xid, mac):
    if len(data) < 240 or data[236:240] != COOKIE:
        return None
    fields = HEADER.unpack(data[:236])
    if fields[0:3] != (2, 1, 6) or fields[4] != xid or fields[11][:6] != mac:
        return None
    return fields[8], options(data[240:])


def dhcp_payload(data):
    """Extract a server reply from an IPv4 packet received before an IP lease exists."""
    if len(data) < 20 or data[0] >> 4 != 4 or data[9] != 17:
        return None
    ihl = (data[0] & 15) * 4
    if ihl < 20 or len(data) < ihl + 8:
        return None
    total = struct.unpack('!H', data[2:4])[0]
    # The probe does not implement fragmented DHCP replies.
    if struct.unpack('!H', data[6:8])[0] & 0x3fff:
        return None
    source, destination, length, _ = struct.unpack('!HHHH', data[ihl:ihl + 8])
    if (source, destination) != (67, 68) or length < 8:
        return None
    if total > len(data) or ihl + length > total:
        return None
    return data[ihl + 8:ihl + length]


def acquire(interface, timeout=5):
    # Raw reception is required before the interface has a routable address;
    # the normal IP input path may discard replies under reverse-path filtering.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock, \
            socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(0x0800)) as receiver:
        receiver.bind((interface, 0))
        request = struct.pack('256s', interface.encode())
        mac = fcntl.ioctl(sock.fileno(), 0x8927, request)[18:24]
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b'\0')
        sock.bind(('0.0.0.0', 68))
        xid = secrets.randbits(32)

        def exchange(message, expected, server=None):
            deadline = time.monotonic() + timeout
            next_send = 0
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now >= next_send:
                    sock.sendto(message, ('255.255.255.255', 67))
                    next_send = now + 1
                receiver.settimeout(min(0.25, max(0.001, deadline - now)))
                try:
                    frame = receiver.recv(4096)
                except socket.timeout:
                    continue
                data = dhcp_payload(frame)
                if data is None:
                    continue
                parsed = reply(data, xid, mac)
                if parsed is None:
                    continue
                address, opts = parsed
                if server is not None and opts.get(54) != server:
                    continue
                if opts.get(53) == b'\x06':
                    raise RuntimeError('DHCP server rejected the request')
                if opts.get(53) == bytes([expected]) and len(opts.get(54, b'')) == 4:
                    return address, opts
            raise TimeoutError(f'No DHCP message type {expected} on {interface}')

        offered, offer = exchange(packet(xid, mac, 1), 2)
        address, ack = exchange(packet(xid, mac, 3, offered, offer[54]), 5, offer[54])
        if address != offered or address == b'\0' * 4:
            raise ValueError('DHCP ACK address differs from the offer')
        mask = socket.inet_ntoa(ack[1])
        prefix = ipaddress.IPv4Network(f'0.0.0.0/{mask}').prefixlen
        return {'address': socket.inet_ntoa(address), 'prefix': prefix,
                'gateway': socket.inet_ntoa(ack[3][:4]),
                'server': socket.inet_ntoa(ack[54]),
                'lease_seconds': struct.unpack('!I', ack[51])[0]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('interface')
    args = parser.parse_args()
    print(json.dumps(acquire(args.interface)))
