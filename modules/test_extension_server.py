import socketserver
import threading
import sublime
from LSP.plugin.core.typing import Enum, Optional, List, Dict


class MessageIds(Enum):
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

    TEST_IDENTIFIER_MESSAGE_FORMAT = "{test_method}({test_class})"
    """MessageFormat to encode test method identifiers."""

    IGNORED_TEST_PREFIX = r"@Ignore: "
    """Test identifier prefix for ignored tests."""

    ASSUMPTION_FAILED_TEST_PREFIX = r"@AssumptionFailure: "
    """Test identifier prefix for tests with assumption failures."""


class TestState(Enum):
    WAITING = "Test has not been run"
    STARTED = "Test is running"
    FAILED = "An assertion has failed"
    ASSUMPTION_FAILED = "An assumption has failed"
    ENDED = "Test run ended successfully"


class Test:
    def __init__(
        self,
        id: int,
        name: str,
        is_suite: bool,
        count: int,
        is_dynamic: bool,
        parent: Optional["Test"],
        display_name: str,
        parameter_types: str,
        unique_id: str,
    ):
        self.id = id
        self.name = name
        self.is_suite = is_suite
        self.count = count
        self.is_dynamic = is_dynamic
        self.parent = parent
        self.display_name = display_name
        self.parameter_types = parameter_types
        self.unique_id = unique_id

        self.ignored = False

        self._state = TestState.WAITING
        self._children = []  # type: List["Test"]
        self._failed = False
        self._trace = None  # type: Optional[str]

        if parent:
            parent._children.append(self)

    def _set_failed(self):
        self._failed = True
        if self.parent:
            self.parent._set_failed()

    def is_failed(self):
        return self._failed

    def get_children(self):
        return self._children.copy()

    def set_state(self, state: TestState):
        self._state = state
        if state == TestState.FAILED or TestState.ASSUMPTION_FAILED:
            self._set_failed()

    def get_state(self):
        self._state

    def set_trace(self, trace: str):
        self._trace = trace

    def get_trace(self) -> Optional[str]:
        return self._trace

    def to_markdown_item(self, indent: int) -> str:
        """Creates a markdown item including the results of this test."""
        return ""


class TestContainer:
    def __init__(self):
        self._by_id = {}  # type: Dict[int, Test]
        self._by_name = {}  # type: Dict[str, Test]
        self._roots = []  # type: List[Test]

    def get_by_name(self, name: str) -> Optional[Test]:
        return self._by_name.get(name, None)

    def get_by_id(self, id: int) -> Optional[Test]:
        return self._by_id.get(id, None)

    def insert(self, test: Test):
        self._by_id[test.id] = test
        self._by_name[test.name] = test

        if not test.parent:
            self._roots.append(test)

    def insert_from_testtree(self, testtree_repr: List[str]) -> Test:
        test = Test(
            int(testtree_repr[0]),  # TODO: AssumptionFailed / Ignore
            testtree_repr[1],
            testtree_repr[2] == "true",
            int(testtree_repr[3]),
            testtree_repr[4] == "true",
            None if testtree_repr[5] == testtree_repr[0] else self.get_by_id(int(testtree_repr[5])),  # Runner returns parent == id for roots
            testtree_repr[6],
            testtree_repr[7],
            testtree_repr[8]
        )
        self.insert(test)
        return test

    def to_markdown_list(self) -> str:
        return ""


class _JunitResultsHandler(socketserver.StreamRequestHandler):
    def handle(self):
        panel = sublime.active_window().create_output_panel("JDTLS Test Log")

        view = sublime.active_window().new_file(
            0, sublime.find_resources("Markdown.sublime-syntax")[0]
        )
        view.set_name("JDTLS Test Results")
        view.set_scratch(True)
        view.run_command(
            "insert",
            {
                "characters": "Collecting results...\n\n_(See: `JDTLS Test Log` panel for a real time log)_"
            },
        )

        container = TestContainer()
        current_test = None  # type: Optional[Test]
        runtime_ms = None  # type: Optional[int]

        while True:
            line = self.rfile.readline().decode().strip()
            if not line:
                break
            panel.run_command("insert", {"characters": line + "\n"})
            header, args = (
                line[: MessageIds.MSG_HEADER_LENGTH],
                line[MessageIds.MSG_HEADER_LENGTH :].split(","),
            )

            if header == MessageIds.TEST_TREE:
                container.insert_from_testtree(args)
            elif header == MessageIds.TEST_START:
                current_test = container.get_by_id(int(args[0]))
                if current_test:
                    current_test.set_state(TestState.STARTED)
            elif header == MessageIds.TEST_FAILED:
                current_test = container.get_by_id(int(args[0]))
                if current_test:
                    if args[1].startswith(MessageIds.ASSUMPTION_FAILED_TEST_PREFIX.value):
                        current_test.set_state(TestState.ASSUMPTION_FAILED)
                    else:
                        current_test.set_state(TestState.FAILED)
            elif header == MessageIds.TEST_END:
                if current_test:
                    current_test.set_state(TestState.ENDED)
                current_test = None
            elif header == MessageIds.TRACE_START:
                trace = ""
                while True:
                    trace_line = self.rfile.readline().decode()
                    if not trace_line:
                        break
                    if trace_line.startswith(MessageIds.TRACE_END.value):
                        break
                if current_test:
                    current_test.set_trace(trace)
            elif header == MessageIds.TEST_RUN_END:
                runtime_ms = int(args[0])

        view.run_command("select_all")
        view.run_command("right_delete")
        view.run_command("insert", {"characters": "Results"})


class JunitResultsServer:
    """TCP Server that connects to https://github.com/eclipse-jdt/eclipse.jdt.ui/blob/master/org.eclipse.jdt.junit.runtime/src/org/eclipse/jdt/internal/junit/runner/RemoteTestRunner.java"""

    def __init__(self):
        self.server = socketserver.TCPServer(("localhost", 0), _JunitResultsHandler)

    def get_port(self) -> int:
        return self.server.socket.getsockname()[1]

    def receive_test_results_async(self):
        """Handles a single request from a worker thread.
        The RemoteTestRunner uses only a single stream request:
        https://github.com/eclipse-jdt/eclipse.jdt.ui/blob/f33d12e0bf97384ac97e71df290684814555db5c/org.eclipse.jdt.junit.runtime/src/org/eclipse/jdt/internal/junit/runner/RemoteTestRunner.java#L653

        After the request the server is shutdown and closed.
        """

        def _handle_single():
            self.server.handle_request()
            self.server.server_close()

        thread = threading.Thread(target=_handle_single, daemon=True)
        thread.start()
