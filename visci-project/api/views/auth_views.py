import logging
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from ..models import CustomUser
from ..serializers import RegisterSerializer, LoginSerializer, GoogleLoginSerializer, LogoutSerializer
from django.core.mail import send_mail
from django.conf import settings
import secrets
from datetime import timedelta

logger = logging.getLogger(__name__)

class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "This is a protected view!"})

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            # Check if user exists but is not verified
            existing_user = CustomUser.objects.filter(email=email).first()
            if existing_user and not existing_user.is_email_verified:
                # Update the existing unverified user
                existing_user.set_password(password)
                existing_user.otp = secrets.randbelow(900000) + 100000
                existing_user.otp_expiry = timezone.now() + timedelta(minutes=10)
                existing_user.save()
                
                # Send OTP email
                try:
                    send_mail(
                        'Verify Your Email',
                        f'Your OTP is {existing_user.otp}. Valid for 10 minutes.',
                        settings.EMAIL_HOST_USER,
                        [email],
                        fail_silently=False,
                    )
                except Exception as e:
                    print(f"Email sending failed: {e}")
                
                user = existing_user
            else:
                # Regular registration for new users
                user = serializer.save()
                
            cache.set(f'otp_{user.email}', user.otp, timeout=600)  # 10 min expiry
            return Response({
                "message": "OTP sent to email",
                "email": user.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        
        if not email or not otp:
            return Response({
                "error": "Both email and otp are required"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        user = CustomUser.objects.filter(email=email).first()
        
        if not user:
            return Response({
                "error": "User not found"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Check both cached OTP and user OTP
        cached_otp = cache.get(f'otp_{email}')
        user_otp = user.otp
        
        if not cached_otp and not user_otp:
            return Response({
                "error": "No OTP found for this user"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Use the OTP that exists
        valid_otp = cached_otp or user_otp
        
        if valid_otp != otp:
            logger.info(f"OTP Mismatch - Provided: {otp}, Stored: {valid_otp}")
            return Response({
                "error": "Invalid OTP"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if user.otp_expiry <= timezone.now():
            return Response({
                "error": "OTP has expired"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Clear both cached and user OTP
        user.is_email_verified = True
        user.otp = None
        user.otp_expiry = None
        user.save()
        cache.delete(f'otp_{email}')
        
        logger.info(f"OTP Verification successful for {email}")
        return Response({
            "message": "Email verified"
        }, status=status.HTTP_200_OK)

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(request, email=serializer.validated_data['email'], password=serializer.validated_data['password'])
            if user and user.is_email_verified:
                refresh = RefreshToken.for_user(user)
                return Response({
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }, status=status.HTTP_200_OK)
            return Response({"error": "Invalid credentials or email not verified"}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    def post(self, request):
        id_token_str = request.data.get("id_token")
        client_id = request.data.get("client_id")

        if not id_token_str:
            return Response({"error": "Missing credential"}, status=400)

        try:
            # Verify the token
            id_info = id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                audience=client_id,
            )

            email = id_info.get("email")
            name = id_info.get("name")
            picture = id_info.get("picture")
            google_id = id_info.get("sub")

            if not email:
                return Response({"error": "Email not found in token"}, status=400)

            # Find or create the user
            user, created = CustomUser.objects.get_or_create(email=email, defaults={
                "username": email.split("@")[0],
                "is_email_verified": True,
                "google_id": google_id
            })

            if not user.google_id:
                user.google_id = google_id
                user.is_email_verified = True
                user.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "email": user.email,
                "name": name,
                "picture": picture,
            })

        except ValueError as e:
            return Response({"error": f"Invalid token: {str(e)}"}, status=400)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if serializer.is_valid():
            try:
                refresh_token = serializer.validated_data['refresh']
                token = RefreshToken(refresh_token)
                token.blacklist()
                return Response({"message": "Logged out"}, status=status.HTTP_200_OK)
            except Exception:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)