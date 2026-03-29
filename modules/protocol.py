"""
Protocol extensions by JDTLS.

https://github.com/redhat-developer/vscode-java/blob/master/src/protocol.ts
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, TypedDict

from typing_extensions import NotRequired

if TYPE_CHECKING:
    from LSP.protocol import Command, MessageType


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
