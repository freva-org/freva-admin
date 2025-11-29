"""Definition of a custom ansible stdout callback."""

from __future__ import absolute_import, division, print_function

from typing import IO, Optional

__metaclass__ = type

DOCUMENTATION = """
    author: DRKZ CLINT
    name: freva_deployment
    type: stdout
    short_description: YAML-ized Ansible screen output and write to log
    description:
        - Ansible output that can be quite a bit easier to read than the
          default JSON formatting.
        - Parse output to a log file at the same time.
    options:
        log_file:
            default: temporary file
            type: str
            description:
                - Set the path to the log file.
            env:
                - name: ANSIBLE_LOG_PATH
    extends_documentation_fragment:
      - default_callback
    requirements:
      - set as stdout in configuration
"""
import json
import os
from tempfile import NamedTemporaryFile
from typing import Optional

from ansible.constants import MODULE_NO_JSON
from ansible.executor.task_result import TaskResult
from ansible.plugins.callback import (
    module_response_deepcopy,
    strip_internal_keys,
)

# -----------------------------------------------------------------------------
# Select a YAML-style base callback that works with multiple Ansible versions
# -----------------------------------------------------------------------------
try:
    # Preferred: built-in yaml callback (ansible-core)
    from ansible.plugins.callback.yaml import (
        CallbackModule as BaseYamlCallback,
    )
except Exception:
    try:
        # Fallback: old community.general yaml callback
        from ansible_collections.community.general.plugins.callback.yaml import (  # noqa: E501
            CallbackModule as BaseYamlCallback,
        )
    except Exception:
        # Last resort: default stdout callback (no YAML formatting, but works)
        from ansible.plugins.callback.default import (
            CallbackModule as BaseYamlCallback,
        )


class CallbackModule(BaseYamlCallback):
    """
    Custom Ansible callback plugin that logs output to a file in single-line JSON format
    and displays output to stdout in YAML format.

    Attributes
    ----------
    CALLBACK_VERSION : float
        Version of the callback plugin.
    CALLBACK_TYPE : str
        Type of the callback plugin.
    CALLBACK_NAME : str
        Name of the callback plugin.
    log_file : IO
        File object for the log file.
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "stdout"
    CALLBACK_NAME = "deployment_plugin"

    def __init__(self) -> None:
        """
        Initializes the callback plugin.

        Parameters
        ----------
        display : Optional[Display], optional
            Ansible display object for managing console output, by default None.
        """
        log_file = (
            os.getenv("DEPLOYMENT_LOG_PATH")
            or NamedTemporaryFile(suffix=".log", delete=False).name
        )
        self.log_file: IO[str] = open(log_file, "w")
        super().__init__()
        self._plugin_options["result_format"] = "yaml"
        self._plugin_options["pretty_results"] = True

    def log_result(self, result: TaskResult) -> None:
        """
        Logs the result as a single-line JSON string to the log file.

        Parameters
        ----------
        result : TaskResult
            Ansible task result object.
        """
        dump = {
            "task": result.task_name,
            "result": strip_internal_keys(
                module_response_deepcopy(result._result)
            ),
        }
        single_line_json = json.dumps(dump).replace("\n", "").replace("\r", "")
        self.log_file.write(single_line_json + "\n")
        self.log_file.flush()

    def v2_runner_on_ok(self, result: TaskResult) -> None:
        if (
            result._task.action not in MODULE_NO_JSON
            or "ansible_job_id" not in result._result
        ):
            self.log_result(result)
        super().v2_runner_on_ok(result)

    def v2_runner_on_async_ok(self, result: TaskResult) -> None:
        if (
            result._task.action not in MODULE_NO_JSON
            or "ansible_job_id" not in result._result
        ):
            self.log_result(result)
        super().v2_runner_on_async_ok(result)

    def __del__(self) -> None:
        """
        Closes the log file when the callback plugin is destroyed.
        """
        self.log_file.close()
