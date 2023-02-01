from .constants import SESSION_NAME
from .utils import LspJdtlsTextCommand

from LSP.plugin import Session, Notification, LspWindowCommand, Request
from LSP.plugin.core.protocol import ExecuteCommandParams


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
