import os

# agent.settings.Settings requires SATELLITE_TOKEN at import time; provide a
# dummy so the agent package can be imported under test.
os.environ.setdefault("SATELLITE_TOKEN", "test-token")
