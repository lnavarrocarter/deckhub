"""Cada módulo expone `async def collect() -> dict`. Para añadir uno, regístralo aquí."""
from . import network, services, steam, storage, system

MODULES = {
    "system": system,
    "storage": storage,
    "network": network,
    "steam": steam,
    "services": services,
}
