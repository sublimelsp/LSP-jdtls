from LSP.plugin.core.protocol import Location, Range
from LSP.plugin.core.typing import IntEnum, List, NotRequired, Optional, TypedDict

ITestNavigationItem = TypedDict(
    "ITestNavigationItem",
    {
        "simpleName": str,
        "fullyQualifiedName": str,
        "uri": str,
        "relevance": int,
        "outOfBelongingProject": bool,
    },
)


ITestNavigationResult = TypedDict(
    "ITestNavigationResult",
    {
        "items": List[ITestNavigationItem],
        "location": Location,
    },
)


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


IJavaTestItem = TypedDict(
    "IJavaTestItem",
    {
        "children": NotRequired[List["IJavaTestItem"]],
        "uri": Optional[str],
        "range": Optional[Range],
        "jdtHandler": str,
        "fullName": str,
        "label": str,
        "id": str,
        "projectName": str,
        "testKind": TestKind,
        "testLevel": TestLevel,
        "uniqueId": NotRequired[str],
        # Identifies a single invocation of a parameterized test.
        # Invocations for which a re-run is possible store their own uniqueId which is provided as part of the result.
        # Methods may store it in order to specify a certain parameter-set to be used when running again.
        "natureIds": NotRequired[List[str]],
        # Optional fields for projects
    },
)

IJUnitLaunchArguments = TypedDict(
    "IJUnitLaunchArguments",
    {
        "workingDirectory": str,
        "mainClass": str,
        "projectName": str,
        "classpath": List[str],
        "modulepath": List[str],
        "vmArguments": List[str],
        "programArguments": List[str],
    },
)
