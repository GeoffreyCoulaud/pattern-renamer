# ruff: noqa: E402

import gettext
import locale
import logging
import os
import platform
import signal
import sys
from typing import cast

import gi  # type: ignore

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk  # type: ignore

from pattern_renamer.main.build_constants import (
    APP_ID,
    APP_SLUG,
    LOCALE_DIR,
    PKG_DATA_DIR,
    PROFILE,
)  # type: ignore
from pattern_renamer.main.main_model import MainModel
from pattern_renamer.main.types.action_names import ActionNames
from pattern_renamer.main.ui.main_window import MainWindow
from pattern_renamer.main.ui.widget_builder.widget_builder import (  # type: ignore
    Arguments,
    InboundProperty,
    build,
)

# HACK - For some reason, command is not the primary on MacOS...
PRIMARY_KEY = "<Meta>" if sys.platform == "darwin" else "<primary>"


class App(Adw.Application):
    """Main application class that initializes the application and its components."""

    __model: MainModel
    __window: MainWindow
    __files_picker: Gtk.FileDialog

    __quit_action: Gio.Action
    __pick_files_action: Gio.Action
    __apply_action: Gio.Action
    __undo_renaming_action: Gio.Action

    __rename_target_action: Gio.Action
    __regex_action: Gio.Action
    __replace_pattern_action: Gio.Action

    def __setup_logging(self) -> None:
        level = logging.DEBUG if PROFILE == "development" else logging.INFO
        logging.basicConfig(level=level)

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.__setup_logging()
        self.__files_picker = Gtk.FileDialog(
            title=_("Select files to rename"),
            modal=True,
        )
        self.__model = MainModel()
        self.__register_actions()

    def __register_actions(self) -> None:
        # Quit action
        self.__quit_action = Gio.SimpleAction.new(name=ActionNames.QUIT)
        self.__quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(self.__quit_action)
        self.set_accels_for_action(
            f"app.{ActionNames.QUIT}",
            [f"{PRIMARY_KEY}q"],
        )

        # Rename target action
        self.__rename_target_action = Gio.PropertyAction.new(
            name=ActionNames.RENAME_TARGET,
            object=self.__model,
            property_name="rename-target",
        )
        self.add_action(self.__rename_target_action)

        # Regex action
        self.__regex_action = Gio.PropertyAction.new(
            name=ActionNames.REGEX,
            object=self.__model,
            property_name="regex",
        )
        self.add_action(self.__regex_action)

        # Replace pattern action
        self.__replace_pattern_action = Gio.PropertyAction.new(
            name=ActionNames.REPLACE_PATTERN,
            object=self.__model,
            property_name="replace-pattern",
        )
        self.add_action(self.__replace_pattern_action)

        # Pick files action
        self.__pick_files_action = Gio.SimpleAction.new(name=ActionNames.PICK_FILES)
        self.add_action(self.__pick_files_action)
        self.__pick_files_action.connect(
            "activate",
            self.__on_files_picker_requested,
        )

        # Apply renaming action
        self.__apply_action = Gio.SimpleAction.new(name=ActionNames.APPLY_RENAMING)
        self.add_action(self.__apply_action)
        self.__apply_action.connect(
            "activate",
            lambda *_: self.__model.apply_renaming(),
        )
        self.set_accels_for_action(
            f"app.{ActionNames.APPLY_RENAMING}",
            [f"{PRIMARY_KEY}Return"],
        )
        self.__model.bind_property(
            source_property="is-apply-enabled",
            target=self.__apply_action,
            target_property="enabled",
            flags=GObject.BindingFlags.SYNC_CREATE,
        )

        # Undo renaming action
        self.__undo_renaming_action = Gio.SimpleAction.new(
            name=ActionNames.UNDO_RENAMING
        )
        self.add_action(self.__undo_renaming_action)
        self.__undo_renaming_action.connect(
            "activate",
            lambda *_: self.__model.undo_renaming(),
        )
        self.set_accels_for_action(
            f"app.{ActionNames.UNDO_RENAMING}",
            [f"{PRIMARY_KEY}z"],
        )
        self.__model.bind_property(
            source_property="is-apply-enabled",
            target=self.__undo_renaming_action,
            target_property="enabled",
            flags=GObject.BindingFlags.SYNC_CREATE,
        )

    def do_activate(self):
        self.__window = build(
            MainWindow
            + Arguments(application=self)
            + InboundProperty(
                source=self.__model,
                source_property="picked-paths",
                target_property="picked-paths",
                flags=(
                    GObject.BindingFlags.SYNC_CREATE
                    | GObject.BindingFlags.BIDIRECTIONAL
                ),
            )
            + InboundProperty(
                source=self.__model,
                source_property="renamed-paths",
                target_property="renamed-paths",
                flags=GObject.BindingFlags.SYNC_CREATE,
            )
            + InboundProperty(
                source=self.__model,
                source_property="rename-target",
                target_property="rename-target",
                flags=GObject.BindingFlags.SYNC_CREATE,
            )
            + InboundProperty(
                source=self.__model,
                source_property="app-state",
                target_property="app-state",
                flags=GObject.BindingFlags.SYNC_CREATE,
            )
            + InboundProperty(
                source=self.__model,
                source_property="mistakes",
                target_property="mistakes",
                flags=GObject.BindingFlags.SYNC_CREATE,
            )
        )
        self.__window.present()

    def __on_files_picker_requested(self, *_args):
        """Make the user select files to rename."""
        self.__files_picker.open_multiple(
            parent=cast(Gtk.Window, self.__window.get_root()),
            callback=self.__on_files_picked,
        )

    def __on_files_picked(self, _source_object, result: Gio.AsyncResult):
        """
        Handle the files picked by the user.

        This is a `Gio.AsyncReadyCallback`<br/>
        https://lazka.github.io/pgi-docs/Gio-2.0/callbacks.html#Gio.AsyncReadyCallback
        """

        try:
            paths_list_model = self.__files_picker.open_multiple_finish(result=result)
        except GLib.Error:
            return

        gio_files = [
            item
            for i in range(paths_list_model.get_n_items())
            if (item := cast(Gio.File | None, paths_list_model.get_item(i))) is not None
        ]
        self.__model.picked_paths = [
            path
            for gio_file in gio_files
            if (path := gio_file.get_path())
            if path is not None
        ]


def main():
    """The application's entry point."""

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Only use bindtextdomain on Linux, as it's not available on macOS
    if platform.system() == "Linux":
        locale.bindtextdomain(APP_SLUG, LOCALE_DIR)

    locale.textdomain(APP_SLUG)
    gettext.install(APP_SLUG, LOCALE_DIR)

    resource = Gio.Resource.load(os.path.join(PKG_DATA_DIR, f"{APP_SLUG}.gresource"))
    resource._register()  #  type: ignore

    app = App()
    return app.run(sys.argv)
