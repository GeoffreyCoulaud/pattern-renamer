from collections.abc import Callable
from pathlib import Path

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # type: ignore

from pattern_renamer.main.types.action_names import ActionNames
from pattern_renamer.main.types.mistakes import (
    InvalidRegexMistake,
    InvalidReplacePatternMistake,
    Mistake,
    RenameDestinationMistake,
)
from pattern_renamer.main.types.rename_target import RenameTarget
from pattern_renamer.main.ui.rename_item import (
    RenameItemData,
    RenameItemLifeCycleManager,
)
from pattern_renamer.main.ui.widget_builder.widget_builder import (
    Children,
    Handlers,
    Properties,
    TypedChild,
    build,
)


class RenamingPage(Adw.NavigationPage):
    """Component for the renaming page of the application."""

    TAG = "renaming-page"

    # --- Inbound properties

    __picked_paths: list[str]

    @GObject.Property(type=object)
    def picked_paths(self):
        return self.__picked_paths

    @picked_paths.setter
    def picked_paths_setter(self, paths: list[str]) -> None:
        self.__picked_paths = paths
        self.__update_items_model()

    __renamed_paths: list[str]

    @GObject.Property(type=object)
    def renamed_paths(self):
        return self.__renamed_paths

    @renamed_paths.setter
    def renamed_paths_setter(self, paths: list[str]) -> None:
        self.__renamed_paths = paths
        self.__update_items_model()

    __rename_target: RenameTarget

    @GObject.Property(type=str)
    def rename_target(self):
        return self.__rename_target

    @rename_target.setter
    def rename_target_setter(self, rename_target: RenameTarget) -> None:
        self.__rename_target = rename_target
        self.__update_items_model()

    __mistakes: list[Mistake]
    __indexed_rename_destination_mistakes: dict[int, RenameDestinationMistake]

    @GObject.Property(type=object)
    def mistakes(self):
        return self.__mistakes

    @mistakes.setter
    def mistakes_setter(self, mistakes: list[Mistake]) -> None:
        """Set the list of mistakes and update the UI accordingly."""

        # HACK - Avoid unset values that only happen at startup.
        if mistakes is None:
            return
        self.__mistakes = mistakes

        ERROR_CSS_CLASS = "error"

        # Update the regex editable
        if any(isinstance(m, InvalidRegexMistake) for m in mistakes):
            self.__regex_editable.add_css_class(ERROR_CSS_CLASS)
        else:
            self.__regex_editable.remove_css_class(ERROR_CSS_CLASS)

        # Update the replace pattern editable
        if any(isinstance(m, InvalidReplacePatternMistake) for m in mistakes):
            self.__replace_pattern_editable.add_css_class(ERROR_CSS_CLASS)
        else:
            self.__replace_pattern_editable.remove_css_class(ERROR_CSS_CLASS)

        # Update the indexed mistakes
        self.__indexed_rename_destination_mistakes = {
            m.culprit_index: m
            for m in mistakes
            if isinstance(m, RenameDestinationMistake)
        }

    # ---

    __items_list_view: Gtk.ListView
    __items_model: Gio.ListStore
    __items_selection_model: Gtk.SelectionModel
    __items_signal_factory: Gtk.SignalListItemFactory
    __items_lifecycle_manager: RenameItemLifeCycleManager

    __regex_editable: Adw.EntryRow
    __replace_pattern_editable: Adw.EntryRow

    def __get_menu_model(self) -> Gio.Menu:
        # Create a radio menu with 3 items for rename target selection.
        rename_target_action = f"app.{ActionNames.RENAME_TARGET}"
        full = Gio.MenuItem.new(label=_("Full path"))
        full.set_action_and_target_value(
            action=rename_target_action,
            target_value=GLib.Variant.new_string(RenameTarget.FULL),
        )
        name = Gio.MenuItem.new(label=_("File name"))
        name.set_action_and_target_value(
            action=rename_target_action,
            target_value=GLib.Variant.new_string(RenameTarget.NAME),
        )
        stem = Gio.MenuItem.new(label=_("File name, without extention"))
        stem.set_action_and_target_value(
            action=rename_target_action,
            target_value=GLib.Variant.new_string(RenameTarget.STEM),
        )

        # Create a Gio.Menu and append the items.
        rename_target_menu = Gio.Menu()
        rename_target_menu.append_item(stem)
        rename_target_menu.append_item(name)
        rename_target_menu.append_item(full)
        menu = Gio.Menu()
        menu.append_item(
            Gio.MenuItem.new_section(
                label=_("Rename target"),
                section=rename_target_menu,
            )
        )

        return menu

    def __build(self) -> None:
        margin = 12
        BOXED_LIST_PROPERTIES = Properties(
            css_classes=["boxed-list"],
            selection_mode=Gtk.SelectionMode.NONE,
        )

        # Header and menu
        menu_button = Gtk.MenuButton + Properties(
            icon_name="open-menu-symbolic", menu_model=self.__get_menu_model()
        )
        apply_button = (
            Gtk.Button
            + Properties(
                action_name=f"app.{ActionNames.APPLY_RENAMING}",
                tooltip_text=_("Rename files with the current settings"),
            )
            + Children(
                Adw.ButtonContent
                + Properties(icon_name="document-save-symbolic", label="Apply")
            )
        )
        header = (
            Adw.HeaderBar
            + Children(Adw.WindowTitle + Properties(title=_("Pattern Renamer")))
            + TypedChild("end", Gtk.Box + Children(apply_button, menu_button))
        )

        # Regex section
        self.__regex_editable = build(
            Adw.EntryRow
            + Properties(title=_("Regular Expression"))
            + Handlers(changed=self.__on_regex_changed)
        )
        self.__replace_pattern_editable = build(
            Adw.EntryRow
            + Properties(title=_("Replace Pattern"))
            + Handlers(changed=self.__on_replace_pattern_changed)
        )
        regex_section = build(
            Gtk.ListBox
            + BOXED_LIST_PROPERTIES
            + Properties(
                margin_top=margin,
                margin_bottom=margin / 2,
                margin_start=margin,
                margin_end=margin,
            )
            + Children(
                self.__regex_editable,
                self.__replace_pattern_editable,
            )
        )

        # Paths view definition
        self.__items_list_view = build(
            Gtk.ListView
            + Properties(
                name="items-list-view",
                css_classes=["card"],
                model=self.__items_selection_model,
                factory=self.__items_signal_factory,
                margin_top=margin / 2,
                margin_bottom=margin,
                margin_start=margin,
                margin_end=margin,
                show_separators=False,
            )
        )
        items_view = build(
            Gtk.ScrolledWindow
            + Properties(
                vexpand=True,
                hscrollbar_policy=Gtk.PolicyType.NEVER,
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            )
            + Children(self.__items_list_view)
        )

        content = build(
            Adw.ToolbarView
            + TypedChild("top", header)
            + TypedChild(
                "content",
                Gtk.Box
                + Properties(orientation=Gtk.Orientation.VERTICAL)
                + Children(regex_section, items_view),
            )
        )

        # Assemble the page
        self.set_can_pop(True)
        self.set_tag(self.TAG)
        self.set_title(_("Rename"))
        self.set_child(content)

    def __init__(self):
        super().__init__()
        self.__items_model = Gio.ListStore.new(item_type=RenameItemData)
        self.__items_selection_model = Gtk.NoSelection.new(model=self.__items_model)
        self.__items_signal_factory = Gtk.SignalListItemFactory()
        self.__items_lifecycle_manager = RenameItemLifeCycleManager()
        self.__items_lifecycle_manager.attach_to(self.__items_signal_factory)
        self.__build()

    def __on_regex_changed(self, editable: Gtk.Editable):
        self.activate_action(
            name=f"app.{ActionNames.REGEX}",
            args=GLib.Variant.new_string(editable.get_text()),
        )

    def __on_replace_pattern_changed(self, editable: Gtk.Editable):
        self.activate_action(
            name=f"app.{ActionNames.REPLACE_PATTERN}",
            args=GLib.Variant.new_string(editable.get_text()),
        )

    def __on_mistake_banner_button_clicked(self, *_args):
        if not self.__mistakes:
            return
        match first := self.__mistakes[0]:
            case InvalidRegexMistake():
                # Regex mistake, focus the regex editable.
                self.__regex_editable.grab_focus()
            case InvalidReplacePatternMistake():
                # Replace pattern mistake, focus the replace pattern editable.
                self.__replace_pattern_editable.grab_focus()
            case RenameDestinationMistake():
                # Destination mistake, focus the item
                self.__items_list_view.grab_focus()
                self.__items_list_view.scroll_to(
                    first.culprit_index, flags=Gtk.ListScrollFlags.FOCUS
                )
            case _:
                # For other mistakes, just log the message.
                print(f"Unhandled mistake: {first.message}")

    def __update_items_model(self) -> None:
        """Update the path pairs model based on the current rename target."""

        # HACK - Avoid unset values that only happen at startup.
        if (
            not self.__picked_paths
            or not self.__renamed_paths
            or not self.__rename_target
        ):
            return

        transform: Callable[[str], str]
        match self.rename_target:
            case RenameTarget.FULL:
                transform = lambda path: path  # noqa: E731
            case RenameTarget.NAME:
                transform = lambda path: Path(path).name  # noqa: E731
            case RenameTarget.STEM:
                transform = lambda path: Path(path).stem  # noqa: E731
            case _:
                raise ValueError(f"Unknown rename target: {self.rename_target}")

        self.__items_model.remove_all()
        for i, (picked, renamed) in enumerate(
            zip(self.__picked_paths, self.__renamed_paths)
        ):
            rename_item_data = RenameItemData(
                picked_path=transform(picked),
                renamed_path=transform(renamed),
                mistake=self.__indexed_rename_destination_mistakes.get(i),
            )
            self.__items_model.append(rename_item_data)
