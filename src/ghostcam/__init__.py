__all__ = ["GhostCam"]


def __getattr__(name):
    if name == "GhostCam":
        from .main import GhostCam

        return GhostCam
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
