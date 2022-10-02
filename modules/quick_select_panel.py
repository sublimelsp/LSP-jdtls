"""
Implements an high level API to query a selection from an user.

Since Quick Panels only support support single selection, ListInputHandler and a dummy command is used.

Usage:
context = QuickSelect(...).show().then( do_something_with_selection )

Inspired by https://github.com/daveleroy/sublime_debugger/blob/master/modules/ui/input.py
"""

import sublime
import sublime_plugin

from LSP.plugin.core.promise import Promise
from LSP.plugin.core.typing import List, Optional, Dict, Any, Callable


class SelectableItem:
    def __init__(
        self,
        label: str,
        value: Any,
        details: str = "",
        annotation: str = "",
        selected: bool = False,
        kind_id: int = sublime.KIND_ID_AMBIGUOUS,
        on_select_confirmed: Callable[[], None] = lambda: None,
    ):
        """
        Constructs a new instance.

        :param      label:      The label that is mached agains the input
        :param      value:      The value that is returned when the selection is done
        :param      details:    The details show below the item
        :param      annotation: The annotation shown to the right of the item
        :param      selected:   If this item should be preselected (only relevant for multi select)
        :param      kind_id:    The kind identifier, controls the icon
        :param      on_select_confirmed: Called when the item was selected and the panel is confirmed
        """
        self.label = label
        self.value = value
        self.details = details
        self.annotation = annotation
        self.selected = selected
        self.kind_id = kind_id
        self.on_select_confirmed = on_select_confirmed
        self._on_select = lambda: self._toggle()   # type: Callable[[], None]
        """
        Called after the user selected the item.
        The panel might be still open and the user might select this this item again (to unselect it).
        The default implementation changes the selection state only.
        """

    def get_kind(self):
        if self.selected:
            return (self.kind_id, "●", "")
        else:
            return (self.kind_id, "○", "")

    def _toggle(self):
        self.selected = not self.selected


class QuickSelect:
    """
    This class can be used to perform a quick select flow.

    By using an ListInputHandler instead of window.show_quick_panel advanced features like
    multi select are possible.
    """

    def __init__(
        self,
        window: Optional[sublime.Window],
        items: List[SelectableItem],
        preselect_index: int = 0,
        placeholder: str = "",
        multi_select: bool = False,
    ):
        self.window = window or sublime.active_window()
        self.items = items
        self.preselect_index = preselect_index
        self.placeholder = placeholder
        self.multi_select = multi_select

        # Used here as Future
        self.promise = Promise(
            lambda _: None
        )  # type: Promise[Optional[List[SelectableItem]]]

    def show(self) -> Promise[Optional[List[SelectableItem]]]:
        return _ListInputHandler(self).show()

    def _get_current_selection(self) -> List[SelectableItem]:
        return list(filter(lambda item: item.selected, self.items))


class _ListInputHandler(sublime_plugin.ListInputHandler):
    """
    The ListInputHandler that is returned from the dummy command "JdtlsQuickSelectCommand".
    """

    # TODO: Is locking necessary?
    __pending_list_input_handler = None  # type: Optional["_ListInputHandler"]

    @classmethod
    def _consume_pending(cls) -> Optional["_ListInputHandler"]:
        """
        Returns a pending quick select and sets it to none.
        """
        pending_list_input_handler = cls.__pending_list_input_handler
        cls.__pending_list_input_handler = None
        return pending_list_input_handler

    @classmethod
    def _has_pending(cls) -> bool:
        return cls.__pending_list_input_handler is not None

    def __init__(self, context: QuickSelect):
        self.context = context
        self.finished = False
        self.current_items = []  # type: List[SelectableItem]

    def show(self) -> Promise[Optional[List[SelectableItem]]]:
        """
        Shows the dialog and returns promise of the selection.

        The promise returns None if the selection was canceled.
        """
        if self.__class__._has_pending():
            raise ValueError("There is already an input handler pending.")
        self.__class__.__pending_list_input_handler = self
        _show_overlay(self.context.window)
        return self.context.promise

    def placeholder(self) -> str:
        return self.context.placeholder

    def initial_text(self) -> str:
        return ""

    def initial_selection(self):
        return []

    def list_items(self):
        def on_confirm():
            self.finished = True

        if self.context.multi_select:
            confirm_item = SelectableItem("Confirm", None, annotation="Accept this selection")
            confirm_item._on_select = on_confirm

            self.current_items = [confirm_item] + self.context.items
            list_input_items = [sublime.ListInputItem(
                confirm_item.label, 0, confirm_item.details, confirm_item.annotation, (sublime.KIND_ID_AMBIGUOUS, "", "")
            )]
        else:
            self.current_items = self.context.items
            list_input_items = []

        for item in self.context.items:
            list_input_item = sublime.ListInputItem(
                item.label, len(list_input_items), item.details, item.annotation, item.get_kind()
            )
            list_input_items.append(list_input_item)
        return (list_input_items, self.context.preselect_index)

    def cancel(self) -> None:
        # self.context.promise._do_resolve(None)
        # sublime.set_timeout(lambda: _hide_overlay(self.context.window))
        pass

    def confirm(self, v: int) -> None:
        self.current_items[v]._on_select()
        self.context.preselect_index = v

        if not self.context.multi_select:
            self.finished = True

        if self.finished:
            selection = self.context._get_current_selection()
            for item in selection:
                item.on_select_confirmed()
            self.context.promise._do_resolve(selection)
        else:
            sublime.set_timeout(lambda: self.show())

    def next_input(
        self, args: Dict[str, Any]
    ) -> Optional[sublime_plugin.CommandInputHandler]:
        # Always return None and show a new panel on our own in confirm()
        # since we need "unselect" too.
        return None


class JdtlsInputCommand(sublime_plugin.WindowCommand):
    """
    This is a dummy command to get the ListInputHandler to show.
    """

    def input(self, args) -> sublime_plugin.CommandInputHandler:
        pending_list_input_handler = _ListInputHandler._consume_pending()

        if not pending_list_input_handler:
            raise ValueError("No pending list input handler.")

        return pending_list_input_handler

    def run(self, **args):
        # This is a dummpy command that is just used to get the ListInputHandler shown.
        ...

    def is_visible(self):
        return _ListInputHandler._has_pending()


def _hide_overlay(window):
    window.run_command(
        "show_overlay",
        {
            "overlay": "command_palette",
            "text": "",
        },
    )
    window.run_command(
        "hide_overlay",
        {
            "overlay": "command_palette",
        },
    )


def _show_overlay(window):
    # First hide all open overlays
    _hide_overlay(window)
    # Then show our own overlay
    window.run_command(
        "show_overlay",
        {
            "overlay": "command_palette",
            "command": "jdtls_input",
        },
    )
