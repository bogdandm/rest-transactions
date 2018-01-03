import json
import socket
from abc import ABCMeta
from functools import partial
from re import match
from typing import Tuple, Union

from tools import transform_json_types
from tools.flask import dejsonify


def receive(socket_obj: socket.SocketType, block=1024) -> bytes:
    """
    Read bytes from socket until find b"\0"

    :param socket_obj:
    :param block:
    :return:
    """
    res = b""
    for b in iter(partial(socket_obj.recv, block), b""):
        res += b
        if b.endswith(b"\0"):
            break
    return res


class ATcpException(Exception, metaclass=ABCMeta):
    status = None
    text = ""


class Tcp500(ATcpException):
    status = 500
    text = "Fail"


class Tcp404(ATcpException):
    status = 404
    text = "Not Found"


class ATcpPacket(metaclass=ABCMeta):
    """
    Encode & decode data in format b"<str>\n<json>\0"
    """

    def __init__(self, header: Union[str, int], data: Union[ATcpException, dict, list, str, int]):
        self.header = header
        if isinstance(data, ATcpException):
            data = {data.__class__.__name__: data.args}
        self.data = data

    @classmethod
    def decode(cls, data: bytes) -> 'ATcpPacket':
        """
        Factory class method
        data should be in format b"*\n*\0" where * is any bytes sequence

        :param data:
        :return:
        """
        try:
            header, js = str(data[:-1], encoding="utf-8").split("\n", 1)
            if match(r"^\W*$", js):
                js = None
            else:
                js = dejsonify(js, need_transform=True)
        except Exception as e:
            raise Tcp500(e)
        return cls(header, js)

    def encode(self) -> bytes:
        if self.data is not None:
            data = json.dumps(transform_json_types(self.data))
        else:
            data = " "
        return bytes(str(self.header) + "\n" + data, encoding="utf-8") + b"\0"

    @property
    def values(self) -> Tuple[str, dict]:
        return self.header, self.data

    def __str__(self):
        return self.header + "\n" + json.dumps(self.data, indent=4)

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.values)


class Request(ATcpPacket):
    pass


class Response(ATcpPacket):
    pass
