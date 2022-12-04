"""
Protocol extensions by JDTLS.

https://github.com/redhat-developer/vscode-java/blob/master/src/protocol.ts
"""

from LSP.plugin.core.protocol import Command, IntEnum, MessageType
from LSP.plugin.core.typing import TypedDict, NotRequired, Any, List


ActionableNotification = TypedDict("ActionableNotification", {
    "severity": MessageType,
    "message": str,
    "data": NotRequired[Any],
    "commands": NotRequired[List[Command]],
})
"""
Called ActionableMessage in vscode extension.
"""


class FeatureStatus(IntEnum):
    disabled = 0
    interactive = 1
    automatic = 2
