import ctypes.util
import subprocess

# https://github.com/aau-ros/aau_multi_robot/blob/master/explorer/scripts/get_interfaces.py

from ctypes import (
    Structure, Union, POINTER,
    pointer, get_errno, cast,
    c_ushort, c_byte, c_void_p, c_char_p, c_uint, c_uint16, c_uint32
)
from socket import AF_INET, AF_INET6, inet_ntop

IWGETID_CMD = "/sbin/iwgetid"
WIRELESS_PROC_FILE = "/proc/net/wireless"


class struct_sockaddr(Structure):
    _fields_ = [
        ('sa_family', c_ushort),
        ('sa_data', c_byte * 14), ]


class struct_sockaddr_in(Structure):
    _fields_ = [
        ('sin_family', c_ushort),
        ('sin_port', c_uint16),
        ('sin_addr', c_byte * 4)]


class struct_sockaddr_in6(Structure):
    _fields_ = [
        ('sin6_family', c_ushort),
        ('sin6_port', c_uint16),
        ('sin6_flowinfo', c_uint32),
        ('sin6_addr', c_byte * 16),
        ('sin6_scope_id', c_uint32)]


class union_ifa_ifu(Union):
    _fields_ = [
        ('ifu_broadaddr', POINTER(struct_sockaddr)),
        ('ifu_dstaddr', POINTER(struct_sockaddr)), ]


class struct_ifaddrs(Structure):
    pass


struct_ifaddrs._fields_ = [
    ('ifa_next', POINTER(struct_ifaddrs)),
    ('ifa_name', c_char_p),
    ('ifa_flags', c_uint),
    ('ifa_addr', POINTER(struct_sockaddr)),
    ('ifa_netmask', POINTER(struct_sockaddr)),
    ('ifa_ifu', union_ifa_ifu),
    ('ifa_data', c_void_p), ]

libc = ctypes.CDLL(ctypes.util.find_library('c'))


def ifap_iter(ifap):
    ifa = ifap.contents
    while True:
        yield ifa
        if not ifa.ifa_next:
            break
        ifa = ifa.ifa_next.contents


def getfamaddr(sa):
    family = sa.sa_family
    addr = None
    if family == AF_INET:
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in)).contents
        addr = inet_ntop(family, sa.sin_addr)
    elif family == AF_INET6:
        sa = cast(pointer(sa), POINTER(struct_sockaddr_in6)).contents
        addr = inet_ntop(family, sa.sin6_addr)
    return family, addr


class NetworkInterface(object):
    def __init__(self, name):
        self.name = name
        self.index = libc.if_nametoindex(name)
        self.addresses = {}

    def __str__(self):
        return "%s [index=%d, IPv4=%s, IPv6=%s]" % (
            self.name, self.index,
            self.addresses.get(AF_INET),
            self.addresses.get(AF_INET6))


def get_network_interfaces():
    ifap = POINTER(struct_ifaddrs)()
    result = libc.getifaddrs(pointer(ifap))
    if result != 0:
        raise OSError(get_errno())
    del result
    try:
        retval = {}
        for ifa in ifap_iter(ifap):
            name = ifa.ifa_name
            i = retval.get(name)
            if not i:
                i = retval[name] = NetworkInterface(name)
            family, addr = getfamaddr(ifa.ifa_addr.contents)
            if addr:
                i.addresses[family] = addr
        return retval.values()
    finally:
        libc.freeifaddrs(ifap)


class NetworkInfo():
    def __init__(self, ifName: str, addr: str, ssid: str, link: str):
        self.ifName = ifName
        self.addr = addr
        self.ssid = ssid
        self.link = link


def getSSID() -> bytes:
    return subprocess.check_output([IWGETID_CMD, "-r"])


def getLinkQuality() -> str:
    with open(WIRELESS_PROC_FILE, "r") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("wlan"):
                parts = line.split()
                if len(parts) > 3:
                    return parts[2]
    return None


def getNetworkInfo() -> NetworkInfo:
    interfaces = get_network_interfaces()
    for ni in interfaces:
        ifName = ni.name.decode("utf-8")
        if ifName != "lo":
            addr = ni.addresses.get(AF_INET)
            ssid = None
            link = None
            if addr is not None and not addr.startswith("10.0.0.10"):
                if not ifName.startswith('eth'):
                    ssidBytes = getSSID()
                    if ssidBytes is not None:
                        ssid = ssidBytes.decode("utf-8").strip()
                        link = getLinkQuality()
                return NetworkInfo(ifName, addr, ssid, link)
    return None
