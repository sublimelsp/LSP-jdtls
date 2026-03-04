from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

import sublime
import sublime_plugin
from LSP.plugin import Request, Session

from . import installer
from .constants import SESSION_NAME
from .utils import LspJdtlsTextCommand

if TYPE_CHECKING:
    from LSP.plugin.core.protocol import ResponseError


class LspJdtlsBuildWorkspace(LspJdtlsTextCommand):
    def run_jdtls_command(self, edit: sublime.Edit, session: Session) -> None:
        params = True
        session.send_request(
            Request[bool, int]("java/buildWorkspace", params),
            self.on_response_async,
            self.on_error_async,
        )

    def on_response_async(self, response: int) -> None:
        window = self.view.window()
        if window is None:
            return
        if response == 0:
            window.status_message("LSP-jdtls: Build failed")
        elif response == 1:
            window.status_message("LSP-jdtls: Build succeeded")
        elif response == 2:
            window.status_message("LSP-jdtls: Build ended with error")
        elif response == 3:
            window.status_message("LSP-jdtls: Build cancelled")

    def on_error_async(self, error: ResponseError) -> None:
        pass


class JdtlsClearData(sublime_plugin.TextCommand):
    def run(self, edit: sublime.Edit) -> None:
        if sublime.ok_cancel_dialog(
            "Are you sure you want to clear " + installer.jdtls_data_path()
        ):
            if os.path.exists(installer.jdtls_data_path()):
                shutil.rmtree(installer.jdtls_data_path())
                self.view.run_command(
                    "lsp_restart_server", {"config_name": SESSION_NAME}
                )
