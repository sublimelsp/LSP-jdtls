from __future__ import annotations


def reload_plugin() -> None:
    import sys
    for m in list(sys.modules.keys()):
        if m.startswith(str(__package__) + ".") and m != __name__:
            del sys.modules[m]


reload_plugin()

from .modules import *
