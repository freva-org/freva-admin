from __future__ import annotations

import curses
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional, cast

import npyscreen
import tomlkit
from npyscreen.wgwidget import Widget

from freva_deployment.utils import AD, asset_dir, config_file

logging.basicConfig(level=logging.DEBUG)
logger: logging.Logger = logging.getLogger("deploy-freva-tui")


class InfoMixin(Widget):
    """Mixin class to extend npyscreen widgets with an infobox."""

    def __init__(
        self,
        *args: Any,
        section: str = "",
        key: str = "",
        info: str = "",
        **kwargs: Any,
    ) -> None:
        name = kwargs.get("name", "Select")
        kwargs["name"] = f"{name}. Press Ctrl+F for more info."
        self.info = info or AD.get_config_info(section, key)
        super().__init__(*args, **kwargs)

    def edit(self) -> None:
        self.parent.current_info = self.info
        super().edit()


class TextInfo(InfoMixin, npyscreen.TitleText):
    """Extend the TitleText widget by an infobox."""


class DictInfo(npyscreen.TitleText):
    """Extend the TitleText widget by an infobox."""

    def __init__(
        self,
        *args: Any,
        section: str = "",
        key: str = "",
        info: str = "",
        value: Optional[dict[str, list[str]]] = None,
        **kwargs: Any,
    ) -> None:
        name = kwargs.get("name", "Select")
        kwargs["name"] = f"{name}. Press Ctrl+F for more info."
        self.info = info or AD.get_config_info(section, key)
        try:
            value_str = tomlkit.dumps(value or {}).strip().replace('"', "")
        except Exception:
            value_str = ""
        super().__init__(
            *args,
            value=value_str,
            **kwargs,
        )

    def edit(self) -> None:
        self.parent.current_info = self.info
        super().edit()

    @property
    def dict_value(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        # Replace colons with '=' to mimic TOML inline table
        user_input = super().value
        cleaned = re.sub(r"(\w+)\s*:", r"\1 =", user_input)
        # Quote bare words (values like aa, bb)
        cleaned = (
            "{"
            + (
                re.sub(
                    r'(?<!["\'])\b([a-zA-Z_][a-zA-Z0-9_-]*)\b(?!["\'])',
                    r'"\1"',
                    cleaned,
                )
                .lstrip("{")
                .rstrip("}")
            )
            + "}"
        )
        try:
            toml_res: dict[str, Any] = tomlkit.loads(f"result = {cleaned}")
        except Exception:
            toml_res = {}
        for key, values in (toml_res.get("result") or {}).items():
            if isinstance(values, str):
                result[key] = [values]
            else:
                result[key] = values

        return result


class FileInfo(InfoMixin, npyscreen.TitleFilename):
    """Extend the TitleFilename widget by an infobox."""


class ComboInfo(InfoMixin, npyscreen.TitleCombo):
    """Extend the TitleCombo widget by an infobox."""


class PasswordInfo(InfoMixin, npyscreen.TitlePassword):
    """Extend the TitlePassword widget by an infobox."""


class CheckboxInfo(InfoMixin, npyscreen.RoundCheckBox):
    """Extend the TitlePassword widget by an infobox."""


class FileSelector(npyscreen.FileSelector):
    """FileSelector widget that allows for filtering file extensions."""

    file_extentions: list[str]
    """List of allowed file extensions."""
    value: str
    """The value of this file selector."""

    def __init__(
        self, *args, file_extentions: str | list[str] = [".toml"], **kwargs
    ) -> None:
        if isinstance(file_extentions, str):
            self.file_extentions = [file_extentions]
        else:
            self.file_extentions = file_extentions
        super().__init__(*args, **kwargs)
        self.how_exited_handers[npyscreen.wgwidget.EXITED_ESCAPE] = self.exit

    def exit(self) -> None:
        """Exit the dialogue."""
        self.wCommand.value = ""
        self.value = ""
        self.exit_editing()

    def update_grid(self) -> None:
        if self.value:
            self.value = os.path.expanduser(self.value)
        if not os.path.exists(self.value):
            self.value = os.getcwd()
        if os.path.isdir(self.value):
            working_dir = Path(self.value)
        else:
            working_dir = Path(self.value).parent
        self.wStatus1.value = working_dir
        file_list, dir_list = [], []
        if working_dir.parent != working_dir:
            dir_list.append("..")
        try:
            for fn in working_dir.glob("*"):
                rel_path = str(fn.relative_to(working_dir))
                if not rel_path.startswith("."):
                    if fn.is_dir():
                        dir_list.append(str(fn) + os.sep)
                    elif fn.suffix in self.file_extentions:
                        file_list.append(str(fn))
        except OSError:
            npyscreen.notify_wait(
                title="Error", message="Could not read specified directory."
            )
        # DOES NOT CURRENTLY WORK - EXCEPT FOR THE WORKING DIRECTORY.  REFACTOR.
        # sort Filelist
        file_list.sort(key=str.casefold)
        dir_list.sort(key=str.casefold)
        if self.sort_by_extension:
            file_list.sort(key=self.get_extension)
        self.wMain.set_grid_values_from_flat_list(
            dir_list + file_list, reset_cursor=False
        )
        self.display()


def selectFile(starting_value: str = "", *args, **keywords):
    F = FileSelector(*args, **keywords)
    F.set_colors()
    F.wCommand.show_bold = True
    if starting_value:
        if not os.path.exists(
            os.path.abspath(os.path.expanduser(starting_value))
        ):
            F.value = os.getcwd()
        else:
            F.value = starting_value
            F.wCommand.value = starting_value
    else:
        F.value = os.getcwd()
    F.update_grid()
    F.edit()
    return F.wCommand.value


class BaseForm(npyscreen.FormMultiPageWithMenus, npyscreen.FormWithMenus):
    """Base class for forms."""

    _num: int = 0
    input_fields: dict[str, tuple[npyscreen.TitleText, bool]] = {}
    """Dictionary of input fields: the key of the dictionary represents the name
       of the key in the in config toml input files. Values represent a tuple of
       npysceen types that display the input information on this key to the
       user and a boolean indicating whether or not this variable is mandatory.
    """
    certificates: list[str] = []
    """The type of certificate files this step needs."""

    playbook_dir: Path = asset_dir / "playbooks"
    """Default playbook location."""

    current_info: Optional[str] = None
    """The currently selected widget."""

    def get_config(self, key) -> dict[str, str | bool | list[str]]:
        """Read the configuration for a step."""
        try:
            cfg = self.parentApp.config[key].copy()
            if not isinstance(cfg, dict):
                cfg = {}
        except (KeyError, AttributeError, TypeError):
            cfg = {}
        return cfg

    @property
    def num(self) -> str:
        """Calculate the number for enumerations of any input field."""
        self._num += 1
        return f"{self._num}. "

    def check_config(
        self,
        notify: bool = True,
    ) -> dict[str, str | dict[str, str | list | int | bool | None]] | None:
        """Check if the from entries are valid."""
        config = {}
        for key, (obj, mandatory) in self.input_fields.items():
            if hasattr(obj, "dict_value"):
                value = obj.dict_value
            elif hasattr(obj, "values"):
                value = obj.values[obj.value]
            else:
                value = obj.value
            if isinstance(value, str):
                if not value and self.use.value and mandatory and notify:
                    msg = f"MISSING ENTRY FOR {self.step}: {obj.name}"
                    npyscreen.notify_confirm(msg, title="ERROR")
                    return None
            config[key] = value
        cfg = config.copy()
        cfg = config
        for key, value in cfg.items():
            if key in self.list_keys:
                cfg[key] = value.split(",")
        return cfg

    def draw_form(self) -> None:
        """Overload the draw_from method from, this is done to add menus."""
        super().draw_form()
        menus = [
            " " + self.__class__.MENU_KEY + ":Main Menu ",
            "^K:Prev. Tab ",
            "^L:Next Tab ",
            "^R:Run ",
            "^S:Save ",
            "^O:Load ",
            "^E:Exit ",
        ]
        y, x = self.display_menu_advert_at()
        for n, menu_advert in enumerate(menus):
            if isinstance(menu_advert, bytes):
                menu_advert = menu_advert.decode("utf-8", "replace")
            X = sum([len(menu) for menu in menus[:n]]) + x
            self.add_line(
                y,
                X,
                menu_advert,
                self.make_attributes_list(menu_advert, curses.A_NORMAL),
                self.columns - X - 1,
            )

    def previews_form(self, *args, **keywords) -> None:
        return self.change_forms(*args, reverse=True, **keywords)

    def change_forms(self, *args, reverse=False, **keywords) -> None:
        """Cycle between the deployment config forms."""
        for step in self.parentApp._steps_lookup.keys():
            if self.name.lower().startswith(step):
                name = step
                break
            elif "rest" in self.name.lower():
                name = "freva_rest"
            elif self.name.lower().startswith("database"):
                name = "db"
                break
        keys = self.parentApp._steps_lookup.keys()
        steps = list(self.parentApp._steps_lookup.values())
        if reverse:
            change_to = dict(zip(keys, [steps[-1]] + steps[:-1]))
        else:
            change_to = dict(zip(keys, steps[1:] + [steps[0]]))
        self.parentApp.current_form = name
        self.parentApp.change_form(change_to[name])

    def run_deployment(self, *args) -> None:
        """Switch to the deployment setup form."""
        self.parentApp.current_form = self.name
        self.parentApp.change_form("SETUP")

    def add_variables(self):
        """Add some environment variables for running the deployment."""
        popup = VarForm()
        popup.edit()
        del popup

    def clear_cache(self):
        """Clear the app cache."""
        with open(self.parentApp.cache_dir / "freva_deployment.json", "w") as f:
            json.dump({}, f, indent=3)
        self.parentApp.reset()

    def setTheme(self, theme: str) -> None:
        self.theme_manager.theme = getattr(npyscreen.Themes, theme)
        self.theme_manager.theme = theme  # getattr(npyscreen.Themes, theme)
        self.parentApp.DEFAULT_THEME = theme
        self.create()
        self.display()
        self.display()

    def show_info(self, *args: Any, **kwargs: Any) -> None:
        """Display an info if present."""
        if isinstance(self.current_info, str):
            npyscreen.notify_confirm(
                self.current_info, title="Detailed Information"
            )

    def create(self) -> None:
        """Setup the form."""
        self.how_exited_handers[npyscreen.wgwidget.EXITED_ESCAPE] = (
            self.parentApp.exit_application
        )
        self.add_handlers({"^F": self.show_info})
        self.add_handlers({"^O": self.parentApp.load_dialog})
        self.add_handlers({"^S": self.parentApp.save_dialog})
        self.add_handlers({"^K": self.previews_form})
        self.add_handlers({"^L": self.change_forms})
        self.add_handlers({"^R": self.run_deployment})
        self.add_handlers({"^E": self.parentApp.exit_application})
        # The menus are created here.
        self.menu = self.add_menu(name="Main Menu", shortcut="^M")
        self.submenu = self.menu.addNewSubmenu("Deployment Menu")
        self._change_form = self.parentApp.change_form
        self.menu.addItemsFromList(
            [
                ("Set Variables", self.add_variables, "^V"),
                ("Save Config", self.parentApp.save_dialog, "^S"),
                ("Load Config", self.parentApp.load_dialog, "^L"),
                ("Run Deployment", self.run_deployment, "^R"),
                ("Clear App Cache", self.clear_cache, "^D"),
                ("Exit Application", self.parentApp.exit_application, "^E"),
            ]
        )
        self.submenu.addItemsFromList(
            [
                ("Core Deployment", self._change_form, "c", "c", ("MAIN",)),
                ("Web Deployment", self._change_form, "w", "w", ("SECOND",)),
                ("DB Deployment", self._change_form, "d", "d", ("THIRD",)),
                (
                    "Freva-Rest Deployment",
                    self._change_form,
                    "s",
                    "s",
                    ("FOURTH",),
                ),
                ("Run Deployment", self.run_deployment, "^R"),
            ]
        )
        self.use = self.add(
            npyscreen.CheckBox,
            max_height=2,
            value=self.step in self.parentApp._steps,
            editable=True,
            name="Check to set up the {}".format(self.step),
            scroll_exit=True,
        )
        self._add_widgets()


class VarForm(npyscreen.FormMultiPageActionWithMenus):
    """Definition of the form that applies the actual deployment."""

    _num: int = 0

    @property
    def num(self) -> str:
        """Calculate the number for enumerations of any input field."""
        self._num += 1
        return f"{self._num}. "

    def create(self):
        npyscreen.setTheme(npyscreen.Themes.ElegantTheme)
        self.cfg = None
        self.keys = []
        self.values = []
        self.cfg = tomlkit.loads(config_file.read_text())
        for key, value in self.cfg["variables"].items():
            self.add_widget_intelligent(
                npyscreen.TitleText, name=f"{self.num}{key}:", value=value
            )
        self.add_widget_intelligent(
            npyscreen.TitleText,
            name="__________________________",
            editable=False,
        )
        self.delete = self.add_widget_intelligent(
            npyscreen.TitleCombo,
            name="Delete Keys",
            value=0,
            relx=4,
            values=[""] + list(self.cfg["variables"].keys()),
        )
        self.add_btn = self.add_widget_intelligent(
            npyscreen.ButtonPress,
            name="Press for new key",
            use_max_space=True,
            when_pressed_function=self._add_new_keys,
        )
        self.add_widget_intelligent(
            npyscreen.TitleText,
            name="__________________________",
            editable=False,
        )

    def _add_new_keys(self, *args, **kwargs) -> None:
        buttons = [self._widgets__.pop(-1), self._widgets__.pop(-1)]  # type: ignore
        self.keys.append(
            self.add_widget_intelligent(
                npyscreen.TitleText,
                name=f"Set a new key:",
                value="",
                editable=True,
            )
        )
        self.values.append(
            self.add_widget_intelligent(
                npyscreen.TitleText,
                name=f"Set a the according value:",
                value="",
                editable=True,
            )
        )

        self._widgets__ = cast(list[Any], self._widgets__ + buttons)  # type: ignore
        self.display()

    def on_ok(self) -> None:
        if self.delete.value > 0:
            key = list(self.cfg["variables"].keys())[self.delete.value - 1]
            del self.cfg["variables"][key]
        for key, value in zip(self.keys, self.values):
            if key.value and value.value:
                self.cfg["variables"][key.value.upper()] = value.value

        toml_str = tomlkit.dumps(self.cfg)
        self.value = self.key = None
        with config_file.open("w", encoding="utf-8") as f_obj:
            f_obj.write(toml_str)
        self.cfg = None

    def on_cancel(self) -> None:
        self.cfg = None
