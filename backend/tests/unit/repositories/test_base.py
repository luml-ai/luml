from luml.infra.exceptions import ApplicationError
from luml.repositories.base import (
    is_foreign_key_violation,
    violated_constraint,
    violates,
)
from luml.repositories.tracks import stage_sync_error
from sqlalchemy.exc import IntegrityError


class _AdapterError(Exception):
    """The DBAPI-level error; the driver error hangs off its ``__cause__``."""


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
    def test_constraint_name_is_read_through_the_cause_chain(self) -> None:
        error = _wrapped(constraint_name="org_member", sqlstate="23505")

        assert violated_constraint(error) == "org_member"
        assert violates(error, "org_member")
        assert not violates(error, "other")
        assert not is_foreign_key_violation(error)

    def test_foreign_key_violations_are_recognised_by_sqlstate(self) -> None:
        error = _wrapped(
            constraint_name="organization_members_organization_id_fkey",
            sqlstate="23503",
        )

        assert is_foreign_key_violation(error)

    def test_errors_without_driver_details_fall_back_to_the_message(self) -> None:
        error = IntegrityError("", {}, Exception('duplicate key "org_member"'))

        assert violated_constraint(error) is None
        assert violates(error, "org_member")
        assert not is_foreign_key_violation(error)

    def test_stage_sync_error_maps_only_the_known_constraints(self) -> None:
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
