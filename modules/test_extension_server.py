import socketserver
import threading
import sublime
import re
import json
from datetime import datetime, timedelta

from LSP.plugin.core.typing import NotRequired, Optional, List, Dict, Literal, Type, Union, TypedDict, Enum

from .utils import filter_lines, get_settings

ICON_SUCCESS = "✔️"
ICON_FAILED = "❌"

AdditionalTestInfo = Literal["dynamic", "suite", "skipped"]


def enable_stack_trace_filter() -> bool:
    return get_settings().get("test.filterStacktrace")


class EclipseTestRunnerMessageIds:
    """See: https://github.com/eclipse-jdt/eclipse.jdt.ui/blob/master/org.eclipse.jdt.junit.runtime/src/org/eclipse/jdt/internal/junit/runner/MessageIds.java"""

    MSG_HEADER_LENGTH = 8
    """The header length of a message, all messages
    have a fixed header length
    """

    ## CLIENT -> SERVER

    TRACE_START = r"%TRACES "
    """Notification that a test trace has started.
    The end of the trace is signaled by a TRACE_END
    message. In between the TRACE_START and TRACE_END
    the stack trace is submitted as multiple lines.
    """
    TRACE_END = r"%TRACEE "
    """Notification that a trace ends."""
    EXPECTED_START = r"%EXPECTS"
    """Notification that the expected result has started.
    The end of the expected result is signaled by a Trace_END.
    """
    EXPECTED_END = r"%EXPECTE"
    """Notification that an expected result ends."""
    ACTUAL_START = r"%ACTUALS"
    """Notification that the expected result has started.
    The end of the expected result is signaled by a Trace_END.
    """
    ACTUAL_END = r"%ACTUALE"
    """Notification that an expected result ends.
    """
    RTRACE_START = r"%RTRACES"
    """Notification that a trace for a reran test has started.
    The end of the trace is signaled by a RTrace_END
    message.
    """
    RTRACE_END = r"%RTRACEE"
    """Notification that a trace of a reran trace ends."""
    TEST_RUN_START = r"%TESTC  "
    """Notification that a test run has started.
    MessageIds.TEST_RUN_START + testCount.toString + " " + version
    """
    TEST_START = r"%TESTS  "
    """Notification that a test has started.
    MessageIds.TEST_START + testID + "," + testName
    """
    TEST_END = r"%TESTE  "
    """Notification that a test has ended.
    TEST_END + testID + "," + testName
    """
    TEST_ERROR = r"%ERROR  "
    """Notification that a test had an error.
    TEST_ERROR + testID + "," + testName.
    After the notification follows the stack trace.
    """
    TEST_FAILED = r"%FAILED "
    """Notification that a test had a failure.
    TEST_FAILED + testID + "," + testName.
    After the notification follows the stack trace.
    """
    TEST_RUN_END = r"%RUNTIME"
    """Notification that a test run has ended.
    TEST_RUN_END + elapsedTime.toString().
    """
    TEST_STOPPED = r"%TSTSTP "
    """Notification that a test run was successfully stopped.
    """
    TEST_RERAN = r"%TSTRERN"
    """Notification that a test was reran.
    TEST_RERAN + testId + " " + testClass + " " + testName + STATUS.
    Status = "OK" or "FAILURE".
    """

    TEST_TREE = r"%TSTTREE"
    """Notification about a test inside the test suite. <br>
    TEST_TREE + testId + "," + testName + "," + isSuite + "," + testcount + "," + isDynamicTest +
    "," + parentId + "," + displayName + "," + parameterTypes + "," + uniqueId <br>
    isSuite = "true" or "false" <br>
    isDynamicTest = "true" or "false" <br>
    parentId = the unique id of its parent if it is a dynamic test, otherwise can be "-1" <br>
    displayName = the display name of the test <br>
    parameterTypes = comma-separated list of method parameter types if applicable, otherwise an
    empty string <br>
    uniqueId = the unique ID of the test provided by JUnit launcher, otherwise an empty string
    See: ITestRunListener2#testTreeEntry
    """

    ## SERVER -> CLIENT

    TEST_STOP = r">STOP   "
    """Request to stop the current test run."""
    TEST_RERUN = r">RERUN  "
    """Request to rerun a test.
    TEST_RERUN + testId + " " + testClass + " "+testName
    """

    ## OTHER

    IGNORED_TEST_PREFIX = r"@Ignore: "
    """Test identifier prefix for ignored tests."""

    ASSUMPTION_FAILED_TEST_PREFIX = r"@AssumptionFailure: "
    """Test identifier prefix for tests with assumption failures."""

    TEST_NAME_FORMAT = r"(.*)\((.*)\)"
    """MessageFormat to encode test method identifiers."""


# See https://github.com/microsoft/vscode-java-test/blob/main/java-extension/com.microsoft.java.test.runner/src/main/java/com/microsoft/java/test/runner/common/TestMessageConstants.java
class TestNgTestMessageName(Enum):
    TEST_STARTED = "testStarted"
    TEST_FINISHED = "testFinished"
    TEST_FAILED = "testFailed"


TestNgTestMessageAttributes = TypedDict("TestNgTestMessageAttributes", {
    "name": str,
    "message": NotRequired[str],
    "trace": NotRequired[str],
    "duration": NotRequired[str]
})


TestNgTestMessageItem = TypedDict("TestNgTestMessageItem", {
    "name": TestNgTestMessageName,
    "attributes": TestNgTestMessageAttributes
})


class Test:
    def __init__(
        self,
        id: Union[int, str],
        name: str,
        is_suite: Optional[bool] = False,
        count: Optional[int] = 1,
        is_dynamic: Optional[bool] = False,
        parent: Optional["Test"] = None,
        display_name: Optional[str] = None,
        parameter_types: Optional[str] = None,
        unique_id: Optional[str] = None,
    ):
        self.id = id
        self.name = name
        # removeprefix is not available in python 3.3
        if self.name.startswith(EclipseTestRunnerMessageIds.IGNORED_TEST_PREFIX):
            self.name = self.name[EclipseTestRunnerMessageIds.IGNORED_TEST_PREFIX:]
        if self.name.startswith(EclipseTestRunnerMessageIds.ASSUMPTION_FAILED_TEST_PREFIX):
            self.name = self.name[EclipseTestRunnerMessageIds.ASSUMPTION_FAILED_TEST_PREFIX:]
        self.count = count
        self.parent = parent
        self.display_name = display_name
        self.parameter_types = parameter_types
        self.unique_id = unique_id
        self.additional_info = []  # type: List[AdditionalTestInfo]

        self._children = []  # type: List["Test"]
        self._failed = False
        self._trace = ""  # type: str
        self._actual = ""  # type: str
        self._expected = ""  # type: str
        self._started = False  # type: bool
        self._runtime = None  # type: Optional[timedelta]
        self._message = None  # type: Optional[str]

        if parent:
            parent._children.append(self)

        if is_suite:
            self.additional_info.append("suite")
        if is_dynamic:
            self.additional_info.append("dynamic")

        match = re.match(EclipseTestRunnerMessageIds.TEST_NAME_FORMAT, self.name)
        self.method_name = match.group(1) if match else None
        self.class_name = match.group(2) if match else None

    def set_failed(self):
        self._failed = True
        # The runner may not send TEST_START :(
        self._started = True
        if self.parent:
            self.parent.set_failed()

    def set_started(self):
        self._started = True
        if self.parent:
            self.parent.set_started()

    def is_failed(self):
        return self._failed

    def get_children(self):
        return self._children.copy()

    def add_message(self, message: str):
        self._message = message

    def get_message(self) -> Optional[str]:
        return self._message

    def append_trace(self, line: str):
        self._trace += line

    def get_trace(self) -> Optional[str]:
        return self._trace

    def append_actual(self, line: str):
        self._actual += line

    def get_actual(self) -> Optional[str]:
        return self._actual

    def append_expected(self, line: str):
        self._expected += line

    def get_expected(self) -> Optional[str]:
        return self._expected

    def set_runtime(self, runtime: timedelta):
        self._runtime = runtime

    def get_runtime(self) -> Optional[timedelta]:
        return self._runtime

    def to_markdown(self, level: int) -> str:
        """Creates a markdown item including the results of this test."""
        additional_info = self.additional_info.copy()  # type: List[str]
        if not self._started:
            additional_info.append("skipped")
        if self._runtime:
            additional_info += [str(self._runtime.total_seconds()) + " s"]

        result = "{padding}- {icon} **{name}** {type}\n".format(
            padding="    " * level,
            name=self.display_name or self.name,
            icon=ICON_FAILED if self.is_failed() else ICON_SUCCESS,
            type="({})".format(", ".join(additional_info)) if additional_info else ""
        )

        inner_padding = "    " * (level + 1)

        def pad(lines: str):
            sep = "\n" + inner_padding
            return sep.join(line for line in lines.split("\n"))

        if self._failed:
            if self._message:
                result += "\n"
                result += inner_padding + "> message: " + pad(self._message).strip() + "\n"

            if self._expected and self._actual:
                result += "\n"
                result += inner_padding + "> expected: " + pad(self._expected).strip() + "<br>\n"
                result += inner_padding + "> but was: " + pad(self._actual).strip() + "\n"

            if self._trace:
                result += "\n"
                result += inner_padding + "<details>\n"
                result += inner_padding + "<summary>Trace</summary>\n\n"
                result += inner_padding + "```\n"
                result += inner_padding + pad(self._trace).strip() + "\n"
                result += inner_padding + "```\n"
                result += inner_padding + "</details>\n"
                result += "\n"

            result += "\n"
        if self._children:
            result += "".join(child.to_markdown(level + 1) for child in self._children)
        return result


class TestContainer:
    def __init__(self):
        self._by_id = {}  # type: Dict[Union[int, str], Test]
        self._roots = []  # type: List[Test]

    def get_by_id(self, id: Union[int, str]) -> Optional[Test]:
        return self._by_id.get(id, None)

    def insert(self, test: Test):
        self._by_id[test.id] = test

        if not test.parent:
            self._roots.append(test)

    def insert_from_testtree(self, testtree_repr: List[str]) -> Test:
        test = Test(
            int(testtree_repr[0]),
            testtree_repr[1],
            testtree_repr[2] == "true",
            int(testtree_repr[3]),
            testtree_repr[4] == "true",
            None
            if testtree_repr[5] == testtree_repr[0]
            else self.get_by_id(
                int(testtree_repr[5])
            ),  # Runner returns parent == id for roots
            testtree_repr[6],
            testtree_repr[7],
            testtree_repr[8],
        )
        self.insert(test)
        return test

    def to_markdown(self, level: int = 0) -> str:
        return "\n".join(root.to_markdown(level) for root in self._roots)


class _TestResultsHandler(socketserver.StreamRequestHandler):

    def prepare(self):
        ...

    def parse(self, container: TestContainer, line: str) -> Optional[str]:
        """Parse one line. The line is provided as-is (including trailing whitespace and newlines).
        Optionally return a status string.
        """
        ...

    def handle(self):
        panel = sublime.active_window().create_output_panel("JDTLS Test Log")

        view = sublime.active_window().new_file(
            0, sublime.find_resources("Markdown.sublime-syntax")[0]
        )
        view.set_name("JDTLS Test Results")
        view.set_scratch(True)
        view.run_command(
            "insert",
            {"characters": "Collecting results...\n\n"},
        )

        container = TestContainer()
        timestamp = datetime.now()

        self.prepare()

        while True:
            bline = self.rfile.readline()
            if bline == b"":
                break
            line = bline.decode()

            panel.run_command("append", {"characters": line})

            output = self.parse(container, line)
            if output:
                view.run_command("append", {"characters": output})

        results = """# Test Results
_{ts}_

{items}
""".format(ts=timestamp.strftime("%Y-%m-%d %H:%M:%S"), items=container.to_markdown(0))

        results += "\n_took: {} s_\n".format((datetime.now() - timestamp).total_seconds())
        view.run_command("select_all")
        view.run_command("right_delete")
        view.run_command("append", {"characters": results})


class _JunitResultsHandler(_TestResultsHandler):

    def prepare(self):
        self.current_test = None  # type: Optional[Test]
        # Used to consume traces, actual, expected
        self.line_consumer = None
        self.stack_trace_filter = [] if not enable_stack_trace_filter() else [
            "org.eclipse.jdt.internal.junit.runner.",
            "org.eclipse.jdt.internal.junit4.runner.",
            "org.eclipse.jdt.internal.junit5.runner.",
            "org.eclipse.jdt.internal.junit.ui.",
            "junit.framework.TestCase",
            "junit.framework.TestResult",
            "junit.framework.TestResult$1",
            "junit.framework.TestSuite",
            "junit.framework.Assert",
            "org.junit.",
            "java.lang.reflect.Method.invoke",
            "sun.reflect.",
            "jdk.internal.reflect.",
        ]

    def parse(self, container: TestContainer, line: str) -> Optional[str]:
        header, args = (
            line[: EclipseTestRunnerMessageIds.MSG_HEADER_LENGTH],
            line[EclipseTestRunnerMessageIds.MSG_HEADER_LENGTH :].rstrip().split(","),
        )

        if header == EclipseTestRunnerMessageIds.TEST_TREE:
            container.insert_from_testtree(args)
        elif header == EclipseTestRunnerMessageIds.TEST_START:
            self.current_test = container.get_by_id(int(args[0]))
            if self.current_test:
                self.current_test.set_started()
                return "Running " + str(self.current_test.display_name or self.current_test.name) + "\n"

        elif header == EclipseTestRunnerMessageIds.TEST_FAILED:
            self.current_test = container.get_by_id(int(args[0]))
            if self.current_test:
                self.current_test.set_failed()
        elif header == EclipseTestRunnerMessageIds.TEST_ERROR:
            self.current_test = container.get_by_id(int(args[0]))
            if self.current_test:
                self.current_test.set_failed()
        elif header == EclipseTestRunnerMessageIds.TEST_END:
            self.current_test = None
        elif header == EclipseTestRunnerMessageIds.TRACE_START and self.current_test:
            self.line_consumer = lambda line: self.current_test.append_trace(filter_lines(line, self.stack_trace_filter)) if self.current_test else ""
        elif header == EclipseTestRunnerMessageIds.ACTUAL_START and self.current_test:
            self.line_consumer = self.current_test.append_actual
        elif header == EclipseTestRunnerMessageIds.EXPECTED_START and self.current_test:
            self.line_consumer = self.current_test.append_expected
        elif header == EclipseTestRunnerMessageIds.TRACE_END:
            self.line_consumer = None
        elif header == EclipseTestRunnerMessageIds.ACTUAL_END:
            self.line_consumer = None
        elif header == EclipseTestRunnerMessageIds.EXPECTED_END:
            self.line_consumer = None
        elif header == EclipseTestRunnerMessageIds.TEST_RUN_END:
            # runtime_ms = int(args[0])
            pass
        elif self.line_consumer:
            self.line_consumer(line)


class _TestNgResultsHandler(_TestResultsHandler):
    LINE_REGEX = r"@@<TestRunner-(.*?)-TestRunner>"
    """Regular expression for a single line. The first group captures the JSON representation."""

    def prepare(self):
        self.stack_trace_filter = [] if not enable_stack_trace_filter() else [
            "com.microsoft.java.test.runner.",
            "org.testng.internal.",
            "org.testng.TestRunner",
            "org.testng.SuiteRunner",
            "org.testng.TestNG",
            "org.testng.Assert",
            "java.lang.reflect.Method.invoke",
            "sun.reflect.",
            "jdk.internal.reflect.",
        ]

    def parse(self, container: TestContainer, line: str) -> Optional[str]:
        match = re.match(self.LINE_REGEX, line.strip())
        if not match:
            return
        json_string = match.group(1)
        data = json.loads(json_string)  # type: TestNgTestMessageItem

        if data["name"] == TestNgTestMessageName.TEST_STARTED:
            test = Test(data["attributes"]["name"], data["attributes"]["name"])
            test.set_started()
            container.insert(test)
            return "Running " + test.name + "\n"
        if data["name"] == TestNgTestMessageName.TEST_FINISHED:
            test = container.get_by_id(data["attributes"]["name"])
            if test:
                if "duration" in data["attributes"]:
                    test.set_runtime(timedelta(seconds=float(data["attributes"]["duration"]) / 1000))
        if data["name"] == TestNgTestMessageName.TEST_FAILED:
            test = container.get_by_id(data["attributes"]["name"])
            if test:
                test.set_failed()
                if "message" in data["attributes"]:
                    test.add_message(data["attributes"]["message"])
                if "trace" in data["attributes"]:
                    test.append_trace(filter_lines(data["attributes"]["trace"], self.stack_trace_filter))
                if "duration" in data["attributes"]:
                    test.set_runtime(timedelta(seconds=float(data["attributes"]["duration"]) / 1000))


class TestResultsServer:
    def __init__(self):
        self.server = socketserver.TCPServer(("localhost", 0), self._get_handler())

    def _get_handler(self) -> Type[_TestResultsHandler]:
        ...

    def get_port(self) -> int:
        return self.server.socket.getsockname()[1]

    def receive_test_results_async(self):
        """Handles a single request from a worker thread.
        The current clients use only a single stream request:
        https://github.com/eclipse-jdt/eclipse.jdt.ui/blob/f33d12e0bf97384ac97e71df290684814555db5c/org.eclipse.jdt.junit.runtime/src/org/eclipse/jdt/internal/junit/runner/RemoteTestRunner.java#L653
        https://github.com/microsoft/vscode-java-test/blob/main/java-extension/com.microsoft.java.test.runner/src/main/java/com/microsoft/java/test/runner/Launcher.java

        After the request the server is shutdown and closed.
        """

        def _handle_single():
            self.server.handle_request()
            self.server.server_close()

        thread = threading.Thread(target=_handle_single, daemon=True)
        thread.start()


class JunitResultsServer(TestResultsServer):
    """TCP Server that receives results from
    https://github.com/eclipse-jdt/eclipse.jdt.ui/blob/master/org.eclipse.jdt.junit.runtime/src/org/eclipse/jdt/internal/junit/runner/RemoteTestRunner.java"""

    def _get_handler(self) -> Type[_TestResultsHandler]:
        return _JunitResultsHandler


class TestNgResultsServer(TestResultsServer):
    """TCP Server that receives results from
    https://github.com/microsoft/vscode-java-test/blob/main/java-extension/com.microsoft.java.test.runner/src/main/java/com/microsoft/java/test/runner/Launcher.java"""

    def _get_handler(self) -> Type[_TestResultsHandler]:
        return _TestNgResultsHandler
