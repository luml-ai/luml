from luml.infra.exceptions import ApplicationError
from luml.repositories.base import (
    is_foreign_key_violation,
    violated_constraint,
    violates,
)
from luml.repositories.tracks import stage_sync_error
from sqlalchemy.exc import IntegrityError


class _AdapterError(Exception):
    pass


class _DriverError(Exception):
    def __init__(
        self, constraint_name: str | None = None, sqlstate: str | None = None
    ) -> None:
        super().__init__("driver error")
        self.constraint_name = constraint_name
        self.sqlstate = sqlstate


def _wrapped(
    constraint_name: str | None = None, sqlstate: str | None = None
) -> IntegrityError:
    adapter = _AdapterError("adapter error")
    adapter.__cause__ = _DriverError(constraint_name, sqlstate)
    return IntegrityError("", {}, adapter)


class TestIntegrityErrorTranslation:
    def test_violated_constraint_returns_name_read_through_cause_chain(self) -> None:
        error = _wrapped(constraint_name="org_member", sqlstate="23505")

        assert violated_constraint(error) == "org_member"
        assert violates(error, "org_member")
        assert not violates(error, "other")
        assert not is_foreign_key_violation(error)

    def test_is_foreign_key_violation_returns_true_when_sqlstate_is_23503(self) -> None:
        error = _wrapped(
            constraint_name="organization_members_organization_id_fkey",
            sqlstate="23503",
        )

        assert is_foreign_key_violation(error)

    def test_violates_falls_back_to_message_when_no_driver_details(self) -> None:
        error = IntegrityError("", {}, Exception('duplicate key "org_member"'))

        assert violated_constraint(error) is None
        assert violates(error, "org_member")
        assert not is_foreign_key_violation(error)

    def test_stage_sync_error_maps_only_known_constraints(self) -> None:
        duplicate = stage_sync_error(_wrapped("uq_track_stages_track_id_name"))
        assigned = stage_sync_error(_wrapped("fk_track_entries_stage_id_track_stages"))
        unrelated = _wrapped("some_other_constraint")

        assert isinstance(duplicate, ApplicationError)
        assert duplicate.status_code == 409
        assert "Duplicate stage names" in duplicate.message
        assert isinstance(assigned, ApplicationError)
        assert assigned.status_code == 409
        assert "assigned to a version" in assigned.message
        assert stage_sync_error(unrelated) is unrelated
