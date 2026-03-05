"""
Implements an high level API to query a selection or a text from an user.

Usage:
QuickSelect(...).show().then( do_something_with_selection )
or:
QuickTextInput(...).show().then( do_something_with_text )

Inspired by https://github.com/daveleroy/sublime_debugger/blob/master/modules/ui/input.py
"""

from __future__ import annotations

from typing import Any, Callable, final
from typing_extensions import override

import sublime
import sublime_plugin
from LSP.plugin.core.promise import Promise, PackagedTask


@final
class SelectableItem:
    def __init__(
        self,
        label: str,
        value: Any,
        details: str = "",
        annotation: str = "",
        kind: tuple[int, str, str] = sublime.KIND_AMBIGUOUS,
        on_select_confirmed: Callable[[], None] = lambda: None,
    ):
        """
        Constructs a new instance.

        :param      label:      The label that is matched against the input
        :param      value:      The value that is returned when the selection is done
        :param      details:    The details show below the item
        :param      annotation: The annotation shown to the right of the item
        :param      kind_id:    The kind identifier, controls the icon
        :param      on_select_confirmed: Called when the item was selected and the panel is confirmed
        """
        self.label = label
        self.value = value
        self.details = details
        self.annotation = annotation
        self.kind = kind
        self.on_select_confirmed = on_select_confirmed


@final
class QuickSelect:
    """
    This class can be used to query a selection from the user.
    """

    def __init__(
        self,
        window: sublime.Window | None,
        items: list[SelectableItem],
        preselect_index: int = 0,
        placeholder: str = "",
        multi_select: bool = False,
    ):
        self._window = window or sublime.active_window()
        self._items = items
        self._preselect_index = preselect_index
        self._placeholder = placeholder
        self._multi_select = multi_select

        # Used here as Future
        packaged_task: PackagedTask[list[SelectableItem] | None] = Promise.packaged_task()
        self._promise = packaged_task[0]
        self._resolve_promise = packaged_task[1]

    def resolve_promise(self, value: list[SelectableItem]) -> None:
        self._resolve_promise(value)

    def show(self) -> Promise[list[SelectableItem] | None]:
        JdtlsInputCommand.enqueue(_ListInputHandler(self))
        JdtlsInputCommand.show(self._window)
        return self._promise


@final
class QuickTextInput:
    """
    This class can be used to query text from the user.
    """

    def __init__(
        self,
        window: sublime.Window | None,
        placeholder: str = "",
        initial_text: str = "",
        validate: Callable[[str], bool] | None = None,
        preview: Callable[[str], str | sublime.Html] | None = None,
    ) -> None:
        self._window = window or sublime.active_window()
        self._placeholder = placeholder
        self._initial_text = initial_text
        self._validate = validate
        self._preview = preview
        packaged_task: PackagedTask[str | None] = Promise.packaged_task()
        self._promise = packaged_task[0]
        self._resolve_promise = packaged_task[1]

    def resolve_promise(self, value: str | None) -> None:
        self._resolve_promise(value)

    def show(self) -> Promise[str | None]:
        JdtlsInputCommand.enqueue(_TextInputHandler(self))
        JdtlsInputCommand.show(self._window)
        return self._promise


@final
class _TextInputHandler(sublime_plugin.TextInputHandler):
    def __init__(self, context: QuickTextInput) -> None:
        self.context = context

    @override
    def placeholder(self) -> str:
        return self.context._placeholder

    @override
    def initial_text(self) -> str:
        return self.context._initial_text

    @override
    def confirm(self, v: str) -> None:
        self.context.resolve_promise(v)

    @override
    def cancel(self) -> None:
        self.context.resolve_promise(None)

    @override
    def validate(self, text: str) -> bool:
        return self.context._validate(text) if self.context._validate else True

    @override
    def preview(self, text: str) -> str | sublime.Html:
        return self.context._preview(text) if self.context._preview else ""


@final
class _ListInputHandler(sublime_plugin.ListInputHandler):
    """
    The ListInputHandler that is returned from the dummy command "JdtlsQuickSelectCommand".
    """

    def __init__(self, context: QuickSelect) -> None:
        self.context = context
        self.finished = False
        self.selected_indices_stack: list[int] = []

    @override
    def placeholder(self) -> str:
        return self.context._placeholder

    @override
    def initial_text(self) -> str:
        return ""

    @override
    def initial_selection(self) -> list[tuple[int, int]]:
        return []

    @override
    def list_items(self) -> tuple[list[sublime.ListInputItem], int]:
        # Value is set to an positive index to self.context.items
        # Value is -1 to signal "confirm"
        list_input_items: list[sublime.ListInputItem] = []

        if self.context._multi_select:
            list_input_items.append(
                sublime.ListInputItem(
                    "Confirm", -1, "", "Accept this selection", sublime.KIND_AMBIGUOUS
                )
            )
        for i, item in enumerate(self.context._items):
            if i not in self.selected_indices_stack:
                list_input_items.append(
                    sublime.ListInputItem(
                        item.label,
                        i,
                        item.details,
                        item.annotation,
                        item.kind,
                    )
                )
        preselect_index = (
            0 if len(self.selected_indices_stack) else self.context._preselect_index
        )
        if self.context._multi_select:
            # Shift because of "Confirm" item
            preselect_index += 1
        return (list_input_items, preselect_index)

    @override
    def cancel(self) -> None:
        if self.selected_indices_stack:
            self.selected_indices_stack.pop()
        else:
            self.context._promise._do_resolve(None)
            # calling _hide_overlay directly crashes sublime :(
            sublime.set_timeout(lambda: _hide_overlay(self.context._window))

    @override
    def confirm(self, v: int) -> None:
        if v == -1:
            self.finished = True
        else:
            self.selected_indices_stack.append(v)

        if not self.context._multi_select:
            self.finished = True

        if self.finished:
            selection = []
            for index in self.selected_indices_stack:
                item = self.context._items[index]
                item.on_select_confirmed()
                selection.append(item)
            self.context._promise._do_resolve(selection)

    @override
    def next_input(
        self, args: dict[str, Any]
    ) -> sublime_plugin.CommandInputHandler | None:
        return None if self.finished else self


class JdtlsInputCommand(sublime_plugin.WindowCommand):
    """
    This is a dummy command to get the ListInputHandler to show.
    """

    # TODO: Is locking necessary?
    __pending_list_input_handler: sublime_plugin.CommandInputHandler | None = (
        None
    )

    @classmethod
    def _consume_pending(cls) -> sublime_plugin.CommandInputHandler | None:
        """
        Returns a pending quick select and sets it to none.
        """
        pending_list_input_handler = cls.__pending_list_input_handler
        cls.__pending_list_input_handler = None
        return pending_list_input_handler

    @classmethod
    def _has_pending(cls) -> bool:
        return cls.__pending_list_input_handler is not None

    @classmethod
    def enqueue(cls, input_handler: sublime_plugin.CommandInputHandler) -> None:
        if cls._has_pending():
            raise ValueError("There is already an input handler pending.")
        cls.__pending_list_input_handler = input_handler

    @classmethod
    def show(cls, window: sublime.Window) -> None:
        if not cls._has_pending():
            raise ValueError("There is no command input handler pending")
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

    @override
    def input(self, args) -> sublime_plugin.CommandInputHandler:
        pending_list_input_handler = self.__class__._consume_pending()

        if not pending_list_input_handler:
            raise ValueError("No pending list input handler.")

        return pending_list_input_handler

    @override
    def run(self, **args) -> None:
        # This is a dummy command that is just used to get the CommandInputHandler shown.
        ...

    @override
    def is_visible(self) -> bool:
        return self.__class__._has_pending()


def _hide_overlay(window: sublime.Window) -> None:
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
