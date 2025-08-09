from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DeviceActivation, MagicLinkToken, UserApprovalRequest

User = get_user_model()


class EmailRequestSerializer(serializers.Serializer):
    """Serializer for email-based magic link requests"""
    email = serializers.EmailField()
    device_fingerprint = serializers.CharField(max_length=255, required=False)
    device_name = serializers.CharField(max_length=100, required=False)
    device_type = serializers.CharField(max_length=50, required=False)


class UserApprovalRequestSerializer(serializers.ModelSerializer):
    """Serializer for user approval requests"""
    device_fingerprint = serializers.CharField(max_length=255, required=False)
    device_name = serializers.CharField(max_length=100, required=False)
    device_type = serializers.CharField(max_length=50, required=False)
    
    class Meta:
        model = UserApprovalRequest
        fields = [
            'email', 'first_name', 'last_name', 'message',
            'device_fingerprint', 'device_name', 'device_type'
        ]
    
    def validate_email(self, value):
        """Ensure email doesn't already exist as an active user"""
        if User.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class MagicLinkActivationSerializer(serializers.Serializer):
    """Serializer for magic link activation"""
    token = serializers.CharField(max_length=64)
    device_fingerprint = serializers.CharField(max_length=255, required=False)
    device_name = serializers.CharField(max_length=100, required=False)
    device_type = serializers.CharField(max_length=50, required=False)


class DeviceActivationSerializer(serializers.ModelSerializer):
    """Serializer for device activation details"""
    user_name = serializers.CharField(source='user.get_display_name', read_only=True)
    
    class Meta:
        model = DeviceActivation
        fields = [
            'id', 'device_fingerprint', 'device_name', 'device_type',
            'activated_at', 'last_used', 'is_active', 'user_name'
        ]
        read_only_fields = ['id', 'activated_at', 'last_used', 'user_name']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile in authentication responses"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    display_name = serializers.CharField(source='get_display_name', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'dharma_name', 'full_name', 'display_name', 'preferred_language',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']