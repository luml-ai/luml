import logging

import uvicorn

from luml_prisma.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)

app = create_app()


def main() -> None:
    uvicorn.run(
        "luml_prisma.server:app",
        host="127.0.0.1",
        port=8420,
    )


if __name__ == "__main__":
    main()
