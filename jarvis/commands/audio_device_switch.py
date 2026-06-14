# audio_device_switch.py
"""
Переключение устройства вывода по умолчанию в Windows (PolicyConfig COM).
"""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

# Константы Windows Audio API
try:
    import comtypes
    from comtypes import CLSCTX_ALL, COMMETHOD, CoCreateInstance, GUID, HRESULT
    from ctypes import c_uint, c_wchar_p

    CLSID_POLICY_CONFIG = GUID("{870af99c-1714-48cf-8120-6a336966be56}")
    IID_POLICY_CONFIG = GUID("{f867965f-42fa-4707-b416-cddcb8724cb2}")

    class IPolicyConfig(comtypes.IUnknown):
        _iid_ = IID_POLICY_CONFIG
        _methods_ = [
            COMMETHOD([], HRESULT, "SetDefaultEndpoint", (["in"], c_wchar_p, "device_id"), (["in"], c_uint, "role")),
        ]

    _COM_TYPES_OK = True
except Exception as exc:
    logger.warning("COM для переключения аудио недоступен: %s", exc)
    _COM_TYPES_OK = False


# Ищет активное устройство вывода по подсказкам в имени
def set_default_playback_device(name_hints: Iterable[str]) -> str | None:
    if not _COM_TYPES_OK:
        return None

    try:
        from pycaw.pycaw import AudioUtilities, ERole

        hints = tuple(h.lower() for h in name_hints if h)
        if not hints:
            return None

        devices = AudioUtilities.GetAllDevices()
        policy = CoCreateInstance(CLSID_POLICY_CONFIG, IPolicyConfig, CLSCTX_ALL)

        for device in devices:
            try:
                # state == 1 — активное устройство
                if getattr(device, "state", None) != 1:
                    continue
                friendly = (getattr(device, "FriendlyName", None) or "").lower()
                if not friendly:
                    continue
                if not any(hint in friendly for hint in hints):
                    continue
                device_id = getattr(device, "id", None) or getattr(device, "Id", None)
                if not device_id:
                    continue
                for role in (ERole.eMultimedia, ERole.eConsole):
                    policy.SetDefaultEndpoint(device_id, role.value)
                return getattr(device, "FriendlyName", None) or friendly
            except Exception as exc:
                logger.debug("Пропуск устройства: %s", exc)

        return None
    except Exception as exc:
        logger.error("set_default_playback_device: %s", exc)
        raise
