"""Deployments: models served by the Satellites of an orbit.

Deployments are created and removed from the web app; the SDK reads them and,
through ``monitoring.py``, their monitoring data.
"""

from luml_api import LumlClient

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
DEPLOYMENT_ID = "0199c455-21ee-74c6-b747-19a82f1a1e75"

luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
)


def main() -> None:
    # Every deployment of the orbit, with its status and monitoring mode
    deployments = luml.deployments.list()
    print(f"All deployments: {deployments}")

    # By name or by id
    by_name = luml.deployments.get("My Deployment")
    print(f"Deployment by name: {by_name}")

    by_id = luml.deployments.get(DEPLOYMENT_ID)
    print(f"Deployment by id: {by_id}")


if __name__ == "__main__":
    main()
