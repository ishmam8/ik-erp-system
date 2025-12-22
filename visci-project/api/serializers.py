from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CustomUser
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
import secrets

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)  # Override to remove UniqueValidator
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['email', 'password']

    def validate(self, attrs):
        email = attrs.get('email')
        existing_user = CustomUser.objects.filter(email=email).first()

        if existing_user:
            if existing_user.is_email_verified:
                raise serializers.ValidationError({
                    'email': 'A verified user with this email already exists.'
                })
            # Handle unverified user case
            existing_user.set_password(attrs.get('password'))
            existing_user.otp = self.generate_otp()
            existing_user.otp_expiry = timezone.now() + timedelta(minutes=10)
            existing_user.save()
            self.context['existing_user'] = existing_user
        return attrs

    def create(self, validated_data):
        if 'existing_user' in self.context:
            user = self.context['existing_user']
        else:
            user = CustomUser.objects.create_user(**validated_data)
            user.otp = self.generate_otp()
            user.otp_expiry = timezone.now() + timedelta(minutes=10)
            user.save()

        self.send_otp_email(user)
        return user

    def generate_otp(self):
        return str(secrets.randbelow(900000) + 100000)

    def send_otp_email(self, user):
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