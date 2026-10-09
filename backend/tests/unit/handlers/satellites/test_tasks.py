import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from luml.handlers.satellites import SatelliteHandler
from luml.infra.exceptions import NotFoundError
from luml.schemas.satellite import (
    SatelliteQueueTask,
    SatelliteTaskStatus,
    SatelliteTaskType,
)

from tests.support.ids import ORBIT_ID, SATELLITE_ID
from tests.support.mocks import CollaboratorMocks


class TestSatelliteTasks:
    async def test_list_tasks_returns_satellite_tasks(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

        expected = [
            SatelliteQueueTask(
                id=task_id,
                satellite_id=SATELLITE_ID,
                orbit_id=ORBIT_ID,
                type=SatelliteTaskType.DEPLOY,
                payload={"created_by_user": "Full Name"},
                status=SatelliteTaskStatus.PENDING,
                scheduled_at=datetime.datetime.now(),
                started_at=datetime.datetime.now(),
                finished_at=None,
                result=None,
                created_at=datetime.datetime.now(),
                updated_at=None,
            )
        ]

        mocks.sat_repo.list_tasks.return_value = expected

        tasks = await mocks.handler.list_tasks(SATELLITE_ID)

        assert tasks == expected
        mocks.sat_repo.list_tasks.assert_awaited_once_with(SATELLITE_ID, None)

    async def test_list_tasks_filters_by_status(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        status = SatelliteTaskStatus.PENDING

        expected = [Mock(status=status), Mock(status=status)]

        mocks.sat_repo.list_tasks.return_value = expected

        tasks = await mocks.handler.list_tasks(SATELLITE_ID, status)

        assert tasks == expected
        assert tasks[0].status == status
        mocks.sat_repo.list_tasks.assert_awaited_once_with(SATELLITE_ID, status)

    async def test_update_task_status_returns_updated_task(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

        status = SatelliteTaskStatus.DONE
        result = {"success": True}

        expected = SatelliteQueueTask(
            id=task_id,
            satellite_id=SATELLITE_ID,
            orbit_id=ORBIT_ID,
            type=SatelliteTaskType.DEPLOY,
            payload={"created_by_user": "Full Name"},
            status=status,
            scheduled_at=datetime.datetime.now(),
            started_at=datetime.datetime.now(),
            finished_at=datetime.datetime.now(),
            result=result,
            created_at=datetime.datetime.now(),
            updated_at=None,
        )
        mocks.sat_repo.update_task_status.return_value = expected

        task = await mocks.handler.update_task_status(
            SATELLITE_ID, task_id, status, result
        )

        assert task == expected
        assert expected.status == status
        assert expected.finished_at
        assert expected.result == result
        mocks.sat_repo.update_task_status.assert_awaited_once_with(
            SATELLITE_ID, task_id, status, result
        )

    async def test_update_task_status_raises_not_found_when_task_missing(
        self, mocks: CollaboratorMocks[SatelliteHandler]
    ) -> None:
        task_id = UUID("0199c419-b7c1-71d6-8382-5697010cee46")

        status = SatelliteTaskStatus.DONE

        mocks.sat_repo.update_task_status.return_value = None

        with pytest.raises(NotFoundError, match="Task not found") as error:
            await mocks.handler.update_task_status(SATELLITE_ID, task_id, status)

        assert error.value.status_code == 404
        mocks.sat_repo.update_task_status.assert_awaited_once_with(
            SATELLITE_ID, task_id, status, None
        )
