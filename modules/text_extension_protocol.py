from LSP.plugin.core.protocol import Location
from LSP.plugin.core.typing import TypedDict, List


ITestNavigationItem = TypedDict('ITestNavigationItem', {
    "simpleName": str,
    "fullyQualifiedName": str,
    "uri": str,
    "relevance": int,
    "outOfBelongingProject": bool,
})


ITestNavigationResult = TypedDict('ITestNavigationResult', {
    "items": List[ITestNavigationItem],
    "location": Location,
})
