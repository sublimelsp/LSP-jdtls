from LSP.plugin import Session, Notification, LspWindowCommand, Request
from LSP.plugin.core.protocol import ExecuteCommandParams

from .utils import LspJdtlsTextCommand
from .constants import SESSION_NAME


class LspJdtlsRefreshWorkspace(LspJdtlsTextCommand):
    def run_jdtls_command(self, edit, session: Session):
        command = {
            "command": "vscode.java.resolveBuildFiles"
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(lambda files: self._send_update_requests(session, files))

    def _send_update_requests(self, session: Session, files):
        for uri in files:
            params = {"uri": uri}
            session.send_notification(
                Notification("java/projectConfigurationUpdate", params)
            )


class DebuggerJdtlsBridgeRequest(LspWindowCommand):
    """Connector bridge to Debugger allowing to send requests to the language server.

    The response is sent back using the specified callback_command (window command).
    The callback command must have the interface def callback(id, error, resp),
    if error is not None then it contains a reason else resp is not None.
    """

    session_name = SESSION_NAME

    def run(self, id, callback_command, method, params, progress=False):
        session = self.session()
        response_args = {"id": id, "error": None, "resp": None}
        if not session:
            response_args["error"] = "No JDTLS session found."
            self.window.run_command(callback_command, response_args)
            return

        def _on_request_success(resp):
            response_args["resp"] = resp
            self.window.run_command(callback_command, response_args)

        def _on_request_error(err):
            response_args["error"] = str(err)
            self.window.run_command(callback_command, response_args)

        session.send_request_async(
            Request(method, params, progress=progress),
            _on_request_success,
            _on_request_error,
        )
