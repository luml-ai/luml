from fastapi import FastAPI, Request
from urllib.parse import urlparse, parse_qs
import json
from copy import deepcopy
import os

from fastapi.responses import Response
import mimetypes


app = FastAPI()


with open("jupyter-lite.json", "r") as f:
    config = json.load(f)

def extractName(referer):
    if referer:
        parsed_url = urlparse(referer)
        query_params = parse_qs(parsed_url.query)
        storage_config = query_params.get("instanceId", ["default"])[0]
        return storage_config
    return "default"


def get_config(referer):
    new_config = deepcopy(config)
    new_config["jupyter-config-data"]["contentsStorageName"] = extractName(referer)
    return json.dumps(new_config)


@app.get("/{path:path}")
async def serve_static(request: Request, path: str):
    # print(f"GET {path} :: {request.headers.get('referer')}")
    file_path = os.path.join(".", path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        if path == "jupyter-lite.json":
            headers = {
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
            return Response(
                get_config(request.headers.get("referer")),
                media_type=mime_type,
                headers=headers,
            )
        else:
            with open(file_path, "rb") as f:
                return Response(content=f.read(), media_type=mime_type)
    return {"detail": "Not Found"}
