""" Client-side handler for workspace/executeCommand """

from .constants import SETTING_ENABLE_NULL_ANALYSIS
from .protocol import FeatureStatus
from .utils import set_lsp_project_setting

from LSP.plugin import Session
from LSP.plugin.core.edit import apply_workspace_edit
from LSP.plugin.core.edit import parse_workspace_edit
from LSP.plugin.core.types import Callable
from LSP.plugin.core.views import location_to_encoded_filename

import sublime


def handle_client_command(session: Session, done: Callable[[], None], command, arguments):
    """
    Returns true if the command was handled.
    """
    client_commands = {
        "java.compile.nullAnalysis.setMode": _set_null_analysis_mode,
        "java.apply.workspaceEdit": _apply_workspace_edit,
        "java.show.references": _show_references,
        # Workaround for https://github.com/eclipse/eclipse.jdt.ls/issues/2362
        "java.completion.onDidSelect": lambda _s, d, *_a: d(),
    }
    if command in client_commands:
        client_commands[command](session, done, *arguments)
        return True
    return False


# HANDLERS
###############################


def _set_null_analysis_mode(session: Session, done: Callable[[], None], status: FeatureStatus):
    mode = "automatic" if status == FeatureStatus.automatic else "disabled"
    set_lsp_project_setting(session.window, SETTING_ENABLE_NULL_ANALYSIS, mode)
    sublime.set_timeout_async(done)


def _apply_workspace_edit(session: Session, done: Callable[[], None], *arguments):
    changes = parse_workspace_edit(arguments[0])
    window = session.window
    sublime.set_timeout(
        lambda: apply_workspace_edit(window, changes).then(
            lambda _: sublime.set_timeout_async(done)
        )
    )


def _show_references(session: Session, done: Callable[[], None], *arguments):
    reflist = []

    def _open_ref_index(index: int, transient: bool = False) -> None:
        if index != -1:
            flags = (
                sublime.ENCODED_POSITION | sublime.TRANSIENT
                if transient
                else sublime.ENCODED_POSITION
            )
            session.window.open_file(reflist[index], flags)

    def _on_ref_choice(index: int) -> None:
        _open_ref_index(index, transient=False)

    def _on_ref_highlight(index: int) -> None:
        _open_ref_index(index, transient=True)

    reflist = [location_to_encoded_filename(r) for r in arguments[2]]  # type: ignore
    session.window.show_quick_panel(
        reflist,
        _on_ref_choice,
        sublime.KEEP_OPEN_ON_FOCUS_LOST,
        0,
        _on_ref_highlight,
    )

    done()
