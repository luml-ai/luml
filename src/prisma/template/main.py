def main(config_path: str = "configs/config.yaml") -> None:
    import json
    import random
    from time import sleep
    for _ in range(10):
        print("sleeping for 1 second...")  # noqa: T201
        sleep(1)

    print(json.dumps({"type": "prisma-message", "metric": random.random()}))  # noqa: T201


if __name__ == "__main__":
    main()
