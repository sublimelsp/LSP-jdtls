import socketserver
import threading
import sublime
from LSP.plugin.core.typing import Enum


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


class _JunitResultsHandler(socketserver.StreamRequestHandler):
    def handle(self):
        view = sublime.active_window().new_file()
        view.set_scratch(True)
        view.set_name("Test Results")

        while True:
            line = self.rfile.readline().strip().decode()
            if not line:
                break
            view.run_command("insert", {"characters": line + "\n"})


class JunitResultsServer:
    """TCP Server that connects to https://github.com/eclipse-jdt/eclipse.jdt.ui/blob/master/org.eclipse.jdt.junit.runtime/src/org/eclipse/jdt/internal/junit/runner/RemoteTestRunner.java
    """

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
