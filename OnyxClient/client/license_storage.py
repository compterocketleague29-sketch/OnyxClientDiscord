import ctypes
import os
from ctypes import wintypes
from pathlib import Path


_ENTROPY = b'ONYX-CLIENT-REMEMBERED-KEY-V1'
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _make_blob(data):
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    return blob, buffer


def _crypt_data(data, unprotect):
    if os.name != 'nt':
        raise OSError('La sauvegarde sécurisée de clé nécessite Windows.')

    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    source, source_buffer = _make_blob(data)
    entropy, entropy_buffer = _make_blob(_ENTROPY)
    result = _DataBlob()

    if unprotect:
        transform = crypt32.CryptUnprotectData
        transform.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
    else:
        transform = crypt32.CryptProtectData
        transform.argtypes = [
            ctypes.POINTER(_DataBlob),
            wintypes.LPCWSTR,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(_DataBlob),
        ]
    transform.restype = wintypes.BOOL

    if unprotect:
        succeeded = transform(
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(result),
        )
    else:
        succeeded = transform(
            ctypes.byref(source),
            'ONYX Client access key',
            ctypes.byref(entropy),
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(result),
        )
    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())

    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(result.pbData, ctypes.c_void_p))


def load_remembered_key(path):
    try:
        encrypted = path.read_bytes()
    except FileNotFoundError:
        return None

    try:
        key = _crypt_data(encrypted, unprotect=True).decode('utf-8')
    except UnicodeDecodeError as error:
        raise OSError('La clé sauvegardée est illisible.') from error
    if not key:
        raise OSError('La clé sauvegardée est vide.')
    return key


def save_remembered_key(path, key):
    if not key:
        raise ValueError('Impossible de sauvegarder une clé vide.')
    encrypted = _crypt_data(key.encode('utf-8'), unprotect=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypted)


def forget_remembered_key(path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass
