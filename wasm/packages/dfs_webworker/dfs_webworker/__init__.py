from dfs_webworker.tabular import tabular_deallocate, tabular_predict, tabular_train
from dfs_webworker.prompt_optimization import (
    prompt_optimization_train,
    prompt_optimization_predict,
)
from dfs_webworker.pyfunc import pyfunc_init, pyfunc_compute, pyfunc_deinit
from dfs_webworker.types import FakeJsProxy
from dfs_webworker.store import Store
import traceback


class Router:
    sync_routes = {}
    async_routes = {}

    @classmethod
    def add_route(cls, route, func, sync=True):
        if sync:
            cls.sync_routes[route] = func
        else:
            cls.async_routes[route] = func


Router.add_route("/tabular/train", tabular_train, sync=True)
Router.add_route("/tabular/predict", tabular_predict, sync=True)
Router.add_route("/tabular/deallocate", tabular_deallocate, sync=True)
Router.add_route("/prompt_optimization/train", prompt_optimization_train, sync=False)
Router.add_route(
    "/prompt_optimization/predict", prompt_optimization_predict, sync=False
)
Router.add_route("/store/deallocate", Store.delete, sync=True)
Router.add_route("/pyfunc/init", pyfunc_init, sync=True)
Router.add_route("/pyfunc/compute", pyfunc_compute, sync=False)
Router.add_route("/pyfunc/deinit", pyfunc_deinit, sync=True)


async def invoke(route: str, payload: FakeJsProxy, debug: bool = False):
    try:
        unwrapped_payload = payload.to_py()
        if route in Router.sync_routes:
            return Router.sync_routes[route](**unwrapped_payload)
        elif route in Router.async_routes:
            return await Router.async_routes[route](**unwrapped_payload)
        raise ValueError(f"Route {route} not found")
    except Exception as e:
        if debug:
            raise e
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
    except KeyboardInterrupt:
        if debug:
            raise KeyboardInterrupt("Execution interrupted by user")
        return {
            "status": "error",
            "error_type": "KeyboardInterrupt",
            "error_message": "Execution interrupted by user",
        }


def ping():
    return "it works!"
