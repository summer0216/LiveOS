from uuid import NAMESPACE_URL, uuid5


def uuid_for(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"liveos-test:{label}"))
