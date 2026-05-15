from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fnnx.extras.reader import Reader

from luml.artifacts._base import (
    DiskReference,
    FileMap,
    MemoryFile,
)
from luml.card.builder import CardBuilder


class ModelReference(DiskReference):
    def validate(self) -> bool:
        try:
            self.read()
            return True
        except Exception as e:
            print(f"Validation failed: {e}")  # noqa: T201
            return False

    def add_model_card(self, html_content: str | CardBuilder) -> None:
        if not isinstance(html_content, str):
            if isinstance(html_content, CardBuilder):
                html_content = html_content.build()
            else:
                msg = "html_content must be a string or CardBuilder instance"
                raise TypeError(msg)

        tag = "dataforce.studio::model_card:v1"

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(
            zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as zip_file:
            zip_file.writestr("index.html", html_content)

        zip_buffer.seek(0)
        file = MemoryFile(zip_buffer.read())

        self._append_metadata(
            idx=None,
            tags=[tag],
            payload={},
            prefix=tag,
            data=[FileMap(file=file, remote_path="model_card.zip")],
        )

    def read(self) -> Reader:
        from fnnx.extras.reader import Reader

        return Reader(self.path)
