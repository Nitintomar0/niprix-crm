from django.urls import re_path

from .consumers import EmployeeLiveLocationConsumer

websocket_urlpatterns = [
    re_path(r"^ws/attendance/live-location/(?P<employee_id>\d+)/$", EmployeeLiveLocationConsumer.as_asgi()),
]
