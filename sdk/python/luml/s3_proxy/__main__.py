import argparse

from luml.s3_proxy.s3proxy import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bucket-server",
        description="S3-compatible proxy server for local file storage",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind to")
    parser.add_argument(
        "--storage", default="./s3_storage", help="Storage root directory"
    )
    parser.add_argument("--access-key", help="AWS access key for authentication")
    parser.add_argument("--secret-key", help="AWS secret key for authentication")
    parser.add_argument("--cors", action="store_true", help="Enable CORS support")
    parser.add_argument(
        "--cors-origins", default="*", help="CORS allowed origins (default: *)"
    )
    parser.add_argument(
        "--cors-methods",
        default="GET, PUT, POST, DELETE, HEAD, OPTIONS",
        help="CORS allowed methods",
    )
    parser.add_argument(
        "--cors-headers",
        default="Authorization, Content-Type, Content-MD5, x-amz-*, Range",
        help="CORS allowed headers",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging (shows detailed auth logs)",
    )

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        storage_root=args.storage,
        access_key=args.access_key,
        secret_key=args.secret_key,
        cors_enabled=args.cors,
        cors_origins=args.cors_origins,
        cors_methods=args.cors_methods,
        cors_headers=args.cors_headers,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
