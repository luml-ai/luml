from dataforce_studio.infra.db import engine
from dataforce_studio.repositories.users import UserRepository
from dataforce_studio.schemas.stats import StatsEmailSendCreate, StatsEmailSendOut


class StatsHandler:
    __user_repository = UserRepository(engine)

    async def create_email_send_stat(
        self, stat: StatsEmailSendCreate
    ) -> StatsEmailSendOut:
        return await self.__user_repository.create_stats_email_send_obj(stat)
