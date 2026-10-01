from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from accounts.models import User
from organizations.models import EmployeeProfile

from .live_location import get_live_location, location_group


class EmployeeLiveLocationConsumer(AsyncJsonWebsocketConsumer):
    """CEO-only subscription to one employee in the CEO's company."""

    async def connect(self):
        user = self.scope.get("user")
        employee_id = int(self.scope["url_route"]["kwargs"]["employee_id"])
        company_id = await self.authorized_company_id(user, employee_id)
        if not company_id:
            await self.close(code=4403)
            return
        self.company_id, self.employee_id = company_id, employee_id
        self.group_name = location_group(company_id, employee_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "location", "state": await self.snapshot(company_id, employee_id)})

    async def disconnect(self, _code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def location_update(self, event):
        await self.send_json({"type": "location", "state": event["state"]})

    @database_sync_to_async
    def authorized_company_id(self, user, employee_id):
        if not user or not user.is_authenticated or not (user.is_superuser or user.role == User.Role.CEO) or not user.company_id:
            return None
        return EmployeeProfile.objects.filter(pk=employee_id, branch__company_id=user.company_id).values_list("branch__company_id", flat=True).first()

    @database_sync_to_async
    def snapshot(self, company_id, employee_id):
        return get_live_location(company_id=company_id, employee_id=employee_id)
