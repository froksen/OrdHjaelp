"""Skærmbillede af alle skærme på Windows med GDI (BitBlt) og en lille PNG-indkoder."""

from __future__ import annotations

import ctypes
import struct
import zlib
from ctypes import wintypes

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
BI_RGB = 0


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def bgra_to_png(width: int, height: int, bgra: bytes) -> bytes:
    """PNG (RGB, 8 bit) ud fra rå BGRA-pixels oppefra og ned, som GetDIBits giver dem."""
    if len(bgra) != width * height * 4:
        raise ValueError("forkert antal bytes til billedet")
    rgb = bytearray(width * height * 3)
    rgb[0::3] = bgra[2::4]
    rgb[1::3] = bgra[1::4]
    rgb[2::3] = bgra[0::4]
    row = width * 3
    raw = b"".join(b"\x00" + bytes(rgb[y * row : (y + 1) * row]) for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8 bit, RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 6))
        + _chunk(b"IEND", b"")
    )


class WindowsScreenshot:
    def capture(self) -> bytes:
        from ordhjaelp.platform.windows import win32

        user32, gdi32 = win32.user32(), win32.gdi32()
        x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        screen_dc = user32.GetDC(None)
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
        old = gdi32.SelectObject(memory_dc, bitmap)
        try:
            if not gdi32.BitBlt(
                memory_dc, 0, 0, width, height, screen_dc, x, y, SRCCOPY | CAPTUREBLT
            ):
                raise OSError(ctypes.get_last_error(), "BitBlt fejlede")
            info = BITMAPINFOHEADER(
                biSize=ctypes.sizeof(BITMAPINFOHEADER),
                biWidth=width,
                biHeight=-height,  # negativ: rækkerne kommer oppefra og ned
                biPlanes=1,
                biBitCount=32,
                biCompression=BI_RGB,
            )
            buffer = ctypes.create_string_buffer(width * height * 4)
            lines = gdi32.GetDIBits(
                memory_dc, bitmap, 0, height, buffer, ctypes.byref(info), DIB_RGB_COLORS
            )
            if lines != height:
                raise OSError(ctypes.get_last_error(), "GetDIBits fejlede")
        finally:
            gdi32.SelectObject(memory_dc, old)
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory_dc)
            user32.ReleaseDC(None, screen_dc)
        return bgra_to_png(width, height, buffer.raw)
