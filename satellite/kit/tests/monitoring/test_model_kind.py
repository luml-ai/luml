import pytest

from luml_satellite.monitoring.compute.models import LocalDeployment
from luml_satellite.monitoring.dashboard.profile import deployment_descriptor, detect_model_kind
from luml_satellite.monitoring.dashboard.schemas import ProfileStatus


class TestModelKind:
    @pytest.mark.parametrize(
        ("manifest", "expected"),
        [
            ({"producer_tags": ["luml.ai::kind_tabular:v1"]}, "tabular"),
            ({"producer_tags": ["luml.ai::kind_llm:v1"]}, "llm"),
            ({"variant": "pyfunc", "producer_tags": []}, "unknown"),
            (None, "unknown"),
        ],
    )
    def test_model_kind_comes_only_from_manifest_tags(
        self, manifest: dict[str, object] | None, expected: str
    ) -> None:
        assert detect_model_kind(manifest) == expected

    def test_profile_and_framework_tags_do_not_imply_model_kind(self) -> None:
        manifest = {
            "variant": "pyfunc",
            "producer_tags": ["luml.ai::sklearn:v1", "luml.ai::tabular_monitoring:v1"],
        }

        assert detect_model_kind(manifest) == "unknown"

    def test_unknown_kind_tag_version_does_not_imply_model_kind(self) -> None:
        assert detect_model_kind({"producer_tags": ["luml.ai::kind_tabular:v9"]}) == "unknown"

    @pytest.mark.parametrize(
        ("manifest", "profile", "expected"),
        [
            ({"producer_tags": ["luml.ai::kind_tabular:v1"]}, None, "tabular"),
            ({"producer_tags": ["luml.ai::kind_llm:v1"]}, None, "llm"),
            (
                {"variant": "pyfunc", "producer_tags": []},
                {
                    "profile_status": "ready",
                    "feature_summaries": {"numerical_features": {"age": {}}},
                },
                "unknown",
            ),
        ],
    )
    def test_header_descriptor_uses_only_manifest_kind_tags(
        self,
        manifest: dict[str, object],
        profile: dict[str, object] | None,
        expected: str,
    ) -> None:
        deployment_id = "019f46e3-3aa1-7672-96a9-8c6d98ab25cd"
        deployment = LocalDeployment(
            deployment_id=deployment_id,
            manifest=manifest,
            reference_profile=profile,
            profile_status=(ProfileStatus.READY if profile else ProfileStatus.ABSENT),
        )

        descriptor = deployment_descriptor(deployment)

        assert descriptor is not None
        assert descriptor["model_kind"] == expected
