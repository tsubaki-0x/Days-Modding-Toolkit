from __future__ import annotations

import ctypes
import os
from pathlib import Path


LOAD_LIBRARY_AS_DATAFILE = 0x00000002
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020


def read_named_resource(executable: Path, name: str, resource_type: str) -> bytes | None:
    """Read a Windows PE resource without executing the target executable."""
    if os.name != "nt":
        raise OSError("Windows PE resource extraction is only available on Windows")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.FindResourceW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
    kernel32.FindResourceW.restype = ctypes.c_void_p
    kernel32.LoadResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.LoadResource.restype = ctypes.c_void_p
    kernel32.LockResource.argtypes = [ctypes.c_void_p]
    kernel32.LockResource.restype = ctypes.c_void_p
    kernel32.SizeofResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.SizeofResource.restype = ctypes.c_uint32
    kernel32.FreeLibrary.argtypes = [ctypes.c_void_p]
    kernel32.FreeLibrary.restype = ctypes.c_int

    flags = LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE
    module = kernel32.LoadLibraryExW(str(executable.resolve()), None, flags)
    if not module:
        error = ctypes.get_last_error()
        raise OSError(error, f"Could not load PE resources from {executable}")

    try:
        resource = kernel32.FindResourceW(module, name, resource_type)
        if not resource:
            return None
        size = kernel32.SizeofResource(module, resource)
        loaded = kernel32.LoadResource(module, resource)
        if not loaded:
            return None
        pointer = kernel32.LockResource(loaded)
        if not pointer:
            return None
        return ctypes.string_at(pointer, size)
    finally:
        kernel32.FreeLibrary(module)


def normalize_ciphercode(resource: bytes) -> bytes:
    """Match GARbro: a 20-byte resource stores the 16-byte key after 4 bytes."""
    if len(resource) == 20:
        return resource[4:20]
    return resource
