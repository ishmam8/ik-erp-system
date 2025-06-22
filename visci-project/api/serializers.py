from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomUser
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import secrets

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.otp = self.generate_otp()
        user.otp_expiry = timezone.now() + timedelta(minutes=10)
        user.save()
        self.send_otp_email(user)
        return user

    def generate_otp(self):
        return str(secrets.randbelow(900000) + 100000)

    def send_otp_email(self, user):
        print("From:", settings.EMAIL_HOST_USER)
        print("From:", settings.DEFAULT_FROM_EMAIL)
        print(f"Sending OTP to: {user.email}")
        from django.core.mail import send_mail
        try:
            send_mail(
                'Verify Your Email',
                f'Your OTP is {user.otp}. Valid for 10 minutes.',
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email sending failed: {e}")

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

class GoogleLoginSerializer(serializers.Serializer):
    code = serializers.CharField()  # OAuth code from frontend

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()