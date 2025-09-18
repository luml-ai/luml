import json
import subprocess


class ComputeWorker:
    def __init__(self, model_envs: dict, extracted_path: str):
        self.model_envs = model_envs
        self.extracted_path = extracted_path
        self.process = None

    def start(self):
        if not self.model_envs:
            return None

        if self.model_envs["path"]:
            env_path = self.model_envs["path"]
            env_name = env_path.split("/")[-1]
        else:
            env_name = self.model_envs["name"]

        worker_script = """
import json
import sys
import asyncio
try:
    import numpy as np
    from fnnx.device import DeviceMap
    from fnnx.runtime import Runtime
    from fnnx.handlers.local import LocalHandlerConfig

    def to_jsonable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, dict):
            return {k: to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [to_jsonable(v) for v in obj]
        if isinstance(obj, tuple):
            return [to_jsonable(v) for v in obj]
        return obj

    extracted_path = sys.argv[1]
    print(json.dumps({"status": "initializing", "extracted_path": extracted_path}), flush=True)
    
    handler = Runtime(
        bundle_path=extracted_path,
        device_map=DeviceMap(accelerator="cpu", node_device_map={}),
        handler_config=LocalHandlerConfig(auto_cleanup=False),
    )
    
    print(json.dumps({"status": "ready"}), flush=True)

    async def process_request(inputs, dynamic_attributes):
        try:
            result = await handler.compute_async(inputs, dynamic_attributes)
        except NotImplementedError:
            result = await asyncio.to_thread(
                handler.compute,
                inputs,
                dynamic_attributes
            )
        return to_jsonable(result)

    while True:
        try:
            line = input()
            data = json.loads(line)

            inputs = data["inputs"]
            dynamic_attributes = data["dynamic_attributes"]

            result = asyncio.run(process_request(inputs, dynamic_attributes))

            print(json.dumps({"success": True, "result": result}), flush=True)

        except EOFError:
            break
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}), flush=True)
            
except Exception as e:
    print(json.dumps({"status": "error", "error": str(e)}), flush=True)
    sys.exit(1)
    """

        cmd = [
            self.model_envs["manager"]._exe,
            "run",
            "-n",
            env_name,
            "python",
            "-c",
            worker_script,
            self.extracted_path,
        ]

        self.process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        try:
            while True:
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError(
                        f"Worker process exited unexpectedly. Stderr: { self.process.stderr.read()}"
                    )

                status_msg = json.loads(line.strip())

                if status_msg.get("status") == "ready":
                    break
                elif status_msg.get("status") == "error":
                    raise RuntimeError(f"Worker initialization failed: {status_msg.get('error')}")
        except Exception as e:
            self.process.terminate()
            raise RuntimeError(f"Failed to start worker: {e}")

        return self.process

    def is_alive(self):
        return self.process and self.process.poll() is None

    async def compute(self, inputs, dynamic_attributes):
        if not self.is_alive():
            raise RuntimeError(
                f"Worker process died unexpectedly. Stderr: {self.process.stderr.read() if self.process else "No process"}"
            )

        try:
            self.process.stdin.write(
                json.dumps({"inputs": inputs, "dynamic_attributes": dynamic_attributes}) + "\n"
            )
            self.process.stdin.flush()

            response_line = self.process.stdout.readline()
            if not response_line:
                raise RuntimeError(f"No response from worker. Stderr: {self.process.stderr.read()}")

            response = json.loads(response_line.strip())

            if response["success"]:
                return response["result"]
            else:
                raise RuntimeError(f"Worker error: {response['error']}")

        except BrokenPipeError as e:
            stderr_output = self.process.stderr.read()
            raise RuntimeError(f"Worker process communication failed: {e}. Stderr: {stderr_output}")

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
