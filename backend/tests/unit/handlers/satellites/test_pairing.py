import datetime
import json
from typing import Any
from unittest.mock import Mock

import pytest
from luml.handlers.satellites import SatelliteHandler
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.schemas.satellite import (
    DEPLOY_FACETS,
    MAX_OPENAPI_DOCUMENT_SIZE_BYTES,
    MONITORING_FACETS,
    MONITORING_FEATURES,
    KitInfo,
    Satellite,
    SatellitePairIn,
    get_present_capabilities,
)
from pydantic import HttpUrl, ValidationError

from tests.support.ids import ORBIT_ID, SATELLITE_ID
from tests.support.mocks import CollaboratorMocks


class TestSatellitePairing:
    async def test_pair_satellite_returns_paired_satellite_with_openapi(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        base_url = "https://satellite.example.com"
        capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}
        openapi = {
            "openapi": "3.1.0",
            "paths": {"/health": {"get": {"summary": "Health"}}},
        }

        unpaired_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url=None,
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )
        expected = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url=base_url,
            paired=True,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=datetime.datetime.now(),
        )

        mocks.sat_repo.get_satellite.return_value = unpaired_satellite
        mocks.sat_repo.pair_satellite.return_value = expected

        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl(base_url),
            capabilities=capabilities,
            openapi=openapi,
        )
        satellite = await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert satellite == expected
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.pair_satellite.assert_awaited_once()
        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        assert pair_call.args[0].openapi == openapi
        assert pair_call.args[0].kit_info is None

    async def test_pair_satellite_stores_kit_info_when_address_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        kit = KitInfo(
            name="luml-satellite",
            version="1.2.3",
            kind="kubernetes",
            api_version=1,
        )
        mocks.sat_repo.get_satellite.return_value = Mock()
        mocks.sat_repo.pair_satellite.return_value = Mock()

        await mocks.handler.pair_satellite(
            SATELLITE_ID,
            SatellitePairIn(
                capabilities={"deploy": {"version": 1}},
                kit=kit,
            ),
        )

        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        paired = pair_call.args[0]
        assert paired.base_url is None
        assert paired.kit_info == kit

    @pytest.mark.parametrize(
        "kit",
        [
            {"name": "", "version": "1", "kind": "docker", "api_version": 1},
            {
                "name": "luml-satellite",
                "version": "1",
                "kind": "docker",
                "api_version": 0,
            },
            {
                "name": "luml-satellite",
                "version": "1",
                "kind": "docker",
                "api_version": "1",
            },
        ],
    )
    def test_pair_satellite_rejects_invalid_kit_info(
        self, kit: dict[str, object]
    ) -> None:
        with pytest.raises(ValidationError, match="kit"):
            SatellitePairIn.model_validate(
                {"capabilities": {"deploy": {"version": 1}}, "kit": kit}
            )

    async def test_pair_satellite_clears_openapi_when_document_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Mock()
        mocks.sat_repo.pair_satellite.return_value = Mock()

        await mocks.handler.pair_satellite(
            SATELLITE_ID,
            SatellitePairIn(
                base_url=HttpUrl("https://satellite.example.com"),
                capabilities={"deploy": {"version": 1}},
            ),
        )

        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        paired = pair_call.args[0]
        assert paired.openapi is None
        assert "openapi" in paired.model_fields_set

    @pytest.mark.parametrize("openapi", [[], "not-an-object", 1, True])
    def test_pair_satellite_rejects_non_object_openapi(self, openapi: object) -> None:
        with pytest.raises(ValidationError, match="openapi"):
            SatellitePairIn.model_validate(
                {
                    "base_url": "https://satellite.example.com",
                    "capabilities": {"deploy": {"version": 1}},
                    "openapi": openapi,
                }
            )

    def test_pair_satellite_accepts_openapi_at_size_cap(self) -> None:
        empty_document_size = len(
            json.dumps(
                {"value": ""}, ensure_ascii=False, separators=(",", ":")
            ).encode()
        )
        document = {
            "value": "x" * (MAX_OPENAPI_DOCUMENT_SIZE_BYTES - empty_document_size)
        }

        satellite = SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={"deploy": {"version": 1}},
            openapi=document,
        )

        assert satellite.openapi == document

    def test_pair_satellite_rejects_openapi_over_size_cap(self) -> None:
        document = {"value": "x" * MAX_OPENAPI_DOCUMENT_SIZE_BYTES}

        with pytest.raises(ValidationError, match="2 MB"):
            SatellitePairIn(
                base_url=HttpUrl("https://satellite.example.com"),
                capabilities={"deploy": {"version": 1}},
                openapi=document,
            )

    async def test_pair_satellite_normalizes_reserved_capabilities(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Mock()
        mocks.sat_repo.pair_satellite.return_value = Mock()
        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={
                "deploy": {
                    "version": 1,
                    "supported_variants": ["pyfunc"],
                    "supported_tags_combinations": [["luml.ai::kind_tabular:v1"]],
                    "extra_fields_form_spec": [],
                    "future_deploy_field": {"enabled": True},
                },
                "monitoring": {"version": 1, "ignored": "value"},
            },
        )

        await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        paired = pair_call.args[0]
        assert paired.capabilities == {
            "deploy": {
                "version": 1,
                "api_versions": [1],
                "facets": DEPLOY_FACETS,
                "supported_variants": ["pyfunc"],
                "supported_tags_combinations": [["luml.ai::kind_tabular:v1"]],
                "extra_fields_form_spec": [],
                "future_deploy_field": {"enabled": True},
            },
            "monitoring": {
                "version": 1,
                "api_versions": [1],
                "facets": MONITORING_FACETS,
                "features": MONITORING_FEATURES,
                "ignored": "value",
            },
        }

    async def test_pair_satellite_stores_custom_capability_verbatim(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        declaration = {
            "version": 1,
            "api_versions": [1],
            "facets": ["deployment:custom.gpu_monitoring"],
            "vendor_setting": {"sample_rate": 0.5},
        }
        mocks.sat_repo.get_satellite.return_value = Mock()
        mocks.sat_repo.pair_satellite.return_value = Mock()

        await mocks.handler.pair_satellite(
            SATELLITE_ID,
            SatellitePairIn(
                base_url=HttpUrl("https://satellite.example.com"),
                capabilities={"custom.gpu_monitoring": declaration},
            ),
        )

        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        paired = pair_call.args[0]
        assert paired.capabilities == {"custom.gpu_monitoring": declaration}

    @pytest.mark.parametrize("capability", ["monitorng", "gpu_monitoring"])
    async def test_pair_satellite_rejects_unknown_unprefixed_capability(
        self, mocks: CollaboratorMocks[SatelliteHandler], capability: str
    ) -> None:
        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={capability: {"version": 1}},
        )

        with pytest.raises(ApplicationError, match=capability) as error:
            await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert error.value.status_code == 422
        mocks.sat_repo.get_satellite.assert_not_awaited()
        mocks.sat_repo.pair_satellite.assert_not_awaited()

    @pytest.mark.parametrize(
        "facet",
        [
            "deployment:monitoring",
            "deployment:gpu",
            "cluster:custom.gpu_monitoring",
        ],
    )
    async def test_pair_satellite_rejects_invalid_custom_facet(
        self, mocks: CollaboratorMocks[SatelliteHandler], facet: str
    ) -> None:
        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={
                "custom.gpu_monitoring": {
                    "version": 1,
                    "facets": [facet],
                }
            },
        )

        with pytest.raises(ApplicationError, match=facet) as error:
            await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert error.value.status_code == 422
        mocks.sat_repo.get_satellite.assert_not_awaited()
        mocks.sat_repo.pair_satellite.assert_not_awaited()

    @pytest.mark.parametrize(
        ("capability", "declaration"),
        [
            ("deploy", {"version": "1"}),
            ("monitoring", {"version": 1, "features": "runtime"}),
            ("monitoring", {"version": 1, "facets": ["satellite:future"]}),
            ("deploy", {"version": 1, "supported_variants": "pyfunc"}),
        ],
    )
    async def test_pair_satellite_rejects_malformed_reserved_capability(
        self,
        mocks: CollaboratorMocks[SatelliteHandler],
        capability: str,
        declaration: dict[str, Any],
    ) -> None:
        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl("https://satellite.example.com"),
            capabilities={capability: declaration},
        )

        with pytest.raises(ApplicationError, match=capability) as error:
            await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert error.value.status_code == 422
        mocks.sat_repo.get_satellite.assert_not_awaited()
        mocks.sat_repo.pair_satellite.assert_not_awaited()

    async def test_pair_satellite_stores_unsupported_reserved_version(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        declaration = {
            "version": 7,
            "facets": ["satellite:future"],
            "future_field": {"value": True},
        }
        mocks.sat_repo.get_satellite.return_value = Mock()
        mocks.sat_repo.pair_satellite.return_value = Mock()

        await mocks.handler.pair_satellite(
            SATELLITE_ID,
            SatellitePairIn(
                base_url=HttpUrl("https://satellite.example.com"),
                capabilities={"monitoring": declaration},
            ),
        )

        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        paired = pair_call.args[0]
        assert paired.capabilities == {"monitoring": declaration}
        assert get_present_capabilities(paired.capabilities) == []

    async def test_pair_satellite_stores_unsupported_api_version(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        mocks.sat_repo.get_satellite.return_value = Mock()
        mocks.sat_repo.pair_satellite.return_value = Mock()

        await mocks.handler.pair_satellite(
            SATELLITE_ID,
            SatellitePairIn(
                base_url=HttpUrl("https://satellite.example.com"),
                capabilities={
                    "monitoring": {"version": 1, "api_versions": [3]},
                },
            ),
        )

        pair_call = mocks.sat_repo.pair_satellite.await_args
        assert pair_call is not None
        paired = pair_call.args[0]
        assert paired.capabilities == {
            "monitoring": {
                "version": 1,
                "api_versions": [3],
                "facets": MONITORING_FACETS,
                "features": MONITORING_FEATURES,
            }
        }
        assert get_present_capabilities(paired.capabilities) == []

    async def test_pair_satellite_raises_bad_request_when_capabilities_empty(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        base_url = "https://satellite.example.com"
        capabilities: dict[str, dict[str, Any]] = {}

        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl(base_url),
            capabilities=capabilities,
        )

        with pytest.raises(ApplicationError, match="Invalid capabilities") as error:
            await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert error.value.status_code == 400

    async def test_pair_satellite_raises_not_found_when_satellite_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        base_url = "https://satellite.example.com"
        capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

        mocks.sat_repo.get_satellite.return_value = None

        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl(base_url),
            capabilities=capabilities,
        )

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert error.value.status_code == 404
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)

    async def test_pair_satellite_raises_not_found_when_pairing_update_returns_nothing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        base_url = "https://satellite.example.com"
        capabilities: dict[str, dict[str, Any]] = {"deploy": {"version": 1}}

        unpaired_satellite = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url=None,
            paired=False,
            capabilities=capabilities,
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite.return_value = unpaired_satellite
        mocks.sat_repo.pair_satellite.return_value = None

        satellite_pair_in = SatellitePairIn(
            base_url=HttpUrl(base_url),
            capabilities=capabilities,
        )

        with pytest.raises(NotFoundError, match="Satellite not found") as error:
            await mocks.handler.pair_satellite(SATELLITE_ID, satellite_pair_in)

        assert error.value.status_code == 404
        mocks.sat_repo.get_satellite.assert_awaited_once_with(SATELLITE_ID)
        mocks.sat_repo.pair_satellite.assert_awaited_once()

    async def test_touch_last_seen_updates_satellite(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        await mocks.handler.touch_last_seen(SATELLITE_ID)

        mocks.sat_repo.touch_last_seen.assert_awaited_once_with(SATELLITE_ID)

    async def test_authenticate_api_key_returns_satellite_by_key_hash(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        expected = Satellite(
            id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            name="test-satellite",
            description=None,
            base_url="https://url.com",
            paired=True,
            capabilities={"deploy": {"version": 1}},
            created_at=datetime.datetime.now(),
            updated_at=None,
            last_seen_at=None,
        )

        mocks.sat_repo.get_satellite_by_hash.return_value = expected

        api_key = "dfssat_test_key_12345"
        result = await mocks.handler.authenticate_api_key(api_key)

        assert result == expected
        mocks.sat_repo.get_satellite_by_hash.assert_awaited_once()
