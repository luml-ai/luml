def main(config_path: str = "configs/config.yaml"):
    import random
    import json
    from time import sleep
    for _ in range(10):
        print("sleeping for 1 second...")
        sleep(1)

    print(json.dumps({"type": "luml-agent-message", "metric": random.random()}))

    return None


if __name__ == "__main__":
    main()
