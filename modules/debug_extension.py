from LSP.plugin import Notification, Session
from LSP.plugin.core.protocol import ExecuteCommandParams  # noqa: F401

from .utils import LspJdtlsTextCommand


class LspJdtlsRefreshWorkspace(LspJdtlsTextCommand):
    def run_jdtls_command(self, edit, session: Session):
        command = {
            "command": "vscode.java.resolveBuildFiles"
        }  # type: ExecuteCommandParams
        session.execute_command(command, False).then(
            lambda files: self._send_update_requests(session, files)
        )

    def _send_update_requests(self, session: Session, files):
        for uri in files:
            params = {"uri": uri}
            session.send_notification(
                Notification("java/projectConfigurationUpdate", params)
            )
