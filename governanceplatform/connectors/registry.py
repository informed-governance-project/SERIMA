from .base import BaseConnector

_registry: dict[str, type[BaseConnector]] = {}


def register(cls: type[BaseConnector]) -> type[BaseConnector]:
    _registry[cls.type_id] = cls
    return cls


def get_connector_class(type_id: str) -> type[BaseConnector]:
    return _registry[type_id]


# Referenced by dotted path in migrations (callable model field choices):
# it must stay importable from this module forever.
def connector_type_choices():
    return [(cls.type_id, cls.label) for cls in _registry.values()]
