"""
Protocol extensions by JDTLS.

https://github.com/redhat-developer/vscode-java/blob/master/src/protocol.ts
"""

from __future__ import annotations

from typing import Any, TypedDict
from typing_extensions import NotRequired

from LSP.plugin.core.protocol import Command, IntEnum, MessageType


class ActionableNotification(TypedDict):
    """Called ActionableMessage in vscode extension."""

    severity: MessageType
    message: str
    data: NotRequired[Any]
    commands: NotRequired[list[Command]]


class FeatureStatus(IntEnum):
    disabled = 0
    interactive = 1
    automatic = 2


class StatusReport(TypedDict):
    message: str
    type: str


class ProgressReport(TypedDict):
    id: NotRequired[str]
    task: str
    subTask: NotRequired[str]
    status: str
    workDone: int
    totalWork: int
    complete: bool
