"""Test bootstrap for the dfs_webworker package.

`dfs_webworker/__init__.py` imports the tabular route, which pulls in `falcon`
(a WASM-only ML stack that is not installable on a plain CPython runner). The
forecasting engine never touches `falcon`, so we stub it out here to let the
package import cleanly during local unit testing.
"""

import sys
import types


def _stub_falcon() -> None:
    if "falcon" in sys.modules:
        return
    falcon = types.ModuleType("falcon")
    falcon.AutoML = object

    tabular = types.ModuleType("falcon.tabular")
    tabular_manager = types.ModuleType("falcon.tabular.tabular_manager")
    tabular_manager.TabularTaskManager = object
    tabular.tabular_manager = tabular_manager

    task_configurations = types.ModuleType("falcon.task_configurations")
    task_configurations.get_task_configuration = lambda *args, **kwargs: None

    falcon.tabular = tabular
    sys.modules["falcon"] = falcon
    sys.modules["falcon.tabular"] = tabular
    sys.modules["falcon.tabular.tabular_manager"] = tabular_manager
    sys.modules["falcon.task_configurations"] = task_configurations


_stub_falcon()
