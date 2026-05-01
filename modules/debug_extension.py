from __future__ import annotations

from typing import TYPE_CHECKING

from LSP.plugin import Notification, Session
from LSP.plugin.core.protocol import Error
from LSP.protocol import ExecuteCommandParams, TextDocumentIdentifier
from typing_extensions import override

from .utils import LspJdtlsTextCommand

if TYPE_CHECKING:
    import sublime


class LspJdtlsRefreshWorkspace(LspJdtlsTextCommand):

    @override
    def run_jdtls_command(self, edit: sublime.Edit, session: Session) -> None:
        command: ExecuteCommandParams = {
            "command": "vscode.java.resolveBuildFiles"
        }
        session.execute_command(command).then(
            lambda files: self._send_update_requests(session, files)
        )

    def _send_update_requests(self, session: Session, files: list[str] | Error | None) -> None:
        if not files or isinstance(files, Error):
            return
        for uri in files:
            session.send_notification(
                Notification[TextDocumentIdentifier]("java/projectConfigurationUpdate", {"uri": uri})
            )
