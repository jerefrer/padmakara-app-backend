from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Magic Link Authentication Flow
    path('auth/request-magic-link/', views.request_magic_link, name='request_magic_link'),
    path('auth/request-approval/', views.request_user_approval, name='request_user_approval'),
    path('auth/activate/<str:token>/', views.activate_device, name='activate_device'),
    
    # Device Management
    path('auth/device/discover/', views.discover_device_activation, name='discover_device_activation'),
    path('auth/device/deactivate/', views.deactivate_device, name='deactivate_device'),
    path('auth/devices/', views.list_user_devices, name='list_user_devices'),
]