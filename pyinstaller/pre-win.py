import locale
import os
import re
import sys
from pathlib import Path

if sys.platform.lower().startswith("win"):
    getlocale = locale.getlocale
    getfilesystemencoding = sys.getfilesystemencoding
    locale.getlocale = lambda: ("utf-8", "utf-8")
    sys.getfilesystemencoding = lambda: "utf-8"
    os.get_blocking = lambda x: True
    try:
        import ansible

        ansible_cli_path = Path(ansible.__file__).parent / "cli" / "__init__.py"
    finally:
        sys.getfilesystemencoding = getfilesystemencoding
        locale.getlocale = getlocale
    ansible_cli_path.write_text(
        re.sub("raise SystemExit", "print", ansible_cli_path.read_text())
    )
    for inp_file in Path(ansible.__file__).parent.rglob("*.py"):
        content = inp_file.read_text(encoding="utf-8")
        write = False
        for call in ("isatty", "get_blocking"):
            if f"os.{call}" in content:
                write = True
                if "import os, termios" not in content:
                    content = content.replace("import os", "import os, termios")
                content = content.replace(f"os.{call}", f"termios.{call}")
        if "get_context('fork')" in content or 'get_context("fork")' in content:
            write = True
            content = content.replace("get_context('fork')", "get_context('spawn')")
            content = content.replace('get_context("fork")', 'get_context("spawn")')
        if "RE_TASKS =" in content:
            for line in content.splitlines():
                if line.startswith("RE_TASKS"):
                    break
            content = content.replace(line, "RE_TASKS = re.compile(u'(?:^|)+tasks?$')")
            write = True
        if write:
            inp_file.write_text(content, encoding="utf-8")
    display = Path(ansible.__file__).parent / "utils" / "display.py"
    content_l = []
    for line in display.read_text(encoding="utf-8").splitlines():
        if line.startswith("_LIBC ="):
            line = ""
        if "fcntl.ioctl" in line:
            line = line.replace(line.strip(), f"tty_size = fcntl.get_terminal_size()")
        content_l.append(line)

    content = (
        "\n".join(content_l)
        .replace("import ctypes.util", "import ctypes.util\nimport wcwidth")
        .replace("_LIBC", "wcwidth")
    )
    display.write_text(content, encoding="utf-8")
else:
    import PyInstaller.depend.bindepend

    bindepend = Path(PyInstaller.depend.bindepend.__file__)
    bindepend.write_text(
        re.sub(
            "encoding='utf-8',",
            "encoding='utf-8', errors='ignore',",
            bindepend.read_text(),
        )
    )
