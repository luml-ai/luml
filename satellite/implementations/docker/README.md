# Docker satellite

This directory holds the Docker satellite: the driver that runs model deployments as
containers on one Docker daemon. `satellite/docker-compose.yml` brings a stand up with the
agent, the telemetry collector and GreptimeDB.

## One network per satellite

The satellite creates its own Docker network, `luml-satellite-<satellite id>`, on the first
deployment and joins it under two aliases: `satellite-agent` and
`satellite-agent-<satellite id>`. Model containers are created in that network and are told
to reach the satellite by the second, satellite-specific name.

Each model container is also connected to the networks the satellite itself belongs to, so
the telemetry collector of its stack stays reachable by name.

Set `DOCKER_NETWORK_NAME` to place model containers in an existing network instead. The
satellite then creates nothing and trusts the name it was given.

## Several satellites on one host

Several satellites can share a daemon. Each is its own process with its own token, and the
ownership rules in the repository root's spec apply: a container carries the identity of the
satellite that started it in `df.satellite_id`, a satellite counts only its own containers as
owned, and orphan cleanup logs every foreign container and leaves it alone.

Give each satellite its own published port and its own token:

```shell
docker run -d --name agent-one \
  --network my-stack_satellite-network \
  --publish 8081:8000 \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --env SATELLITE_TOKEN="$FIRST_TOKEN" \
  --env PLATFORM_URL=https://api.luml.ai \
  --env BASE_URL=http://localhost:8081 \
  luml-satellite-agent:latest
```

Their model containers stay apart because each satellite addresses its own network, and the
satellite-specific alias means a model reaches its own satellite even when two of them share
a network.
