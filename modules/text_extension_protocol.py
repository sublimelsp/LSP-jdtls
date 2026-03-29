from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, TypedDict

from typing_extensions import NotRequired

if TYPE_CHECKING:
    from LSP.protocol import Location, Range


class ITestNavigationItem(TypedDict):
    simpleName: str
    fullyQualifiedName: str
    uri: str
    relevance: int
    outOfBelongingProject: bool


class ITestNavigationResult(TypedDict):
    items: list[ITestNavigationItem]
    location: Location


class TestKind(IntEnum):
    JUnit5 = 0
    JUnit = 1
    TestNG = 2
    Unknown = 100  # Called None in the VSCode extension


class TestLevel(IntEnum):
    Root = 0
    Workspace = 1
    WorkspaceFolder = 2
    Project = 3
    Package = 4
    Class = 5
    Method = 6
    Invocation = 7


class IJavaTestItem(TypedDict):
    children: NotRequired[list[IJavaTestItem]]
    uri: str | None
    range: Range | None
    jdtHandler: str
    fullName: str
    label: str
    id: str
    projectName: str
    testKind: TestKind
    testLevel: TestLevel
    uniqueId: NotRequired[str]
    natureIds: NotRequired[list[str]]


class IJUnitLaunchArguments(TypedDict):
    workingDirectory: str
    mainClass: str
    projectName: str
    classpath: list[str]
    modulepath: list[str]
    vmArguments: list[str]
    programArguments: list[str]
