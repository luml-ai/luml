from fastapi import APIRouter

from dataforce_studio.handlers.stats import StatsHandler
from dataforce_studio.schemas.stats import StatsEmailSendCreate, StatsEmailSendOut

email_routers = APIRouter(prefix="/stats", tags=["stats"])

stats_handler = StatsHandler()


@email_routers.post("/email-send", response_model=StatsEmailSendOut)
async def get_available_organizations(stat: StatsEmailSendCreate) -> StatsEmailSendOut:
    return await stats_handler.create_email_send_stat(stat)
