import argparse

from luml.s3_proxy.s3proxy import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="s3-proxy",
        description="S3-compatible proxy server for local file storage",
    )
    parser.add_argument("--port", type=int, default=9000, help="Port to bind to")
    parser.add_argument(
        "--storage", default="./s3_storage", help="Storage root directory"
    )
    parser.add_argument("--access-key", help="AWS access key for authentication")
    parser.add_argument("--secret-key", help="AWS secret key for authentication")
    parser.add_argument("--cors", action="store_true", help="Enable CORS support")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    run_server(
        port=args.port,
        storage_root=args.storage,
        access_key=args.access_key,
        secret_key=args.secret_key,
        cors_enabled=args.cors,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
