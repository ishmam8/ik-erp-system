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

logger = logging.getLogger(__name__)

class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": "This is a protected view!"})

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            cache.set(f'otp_{user.email}', user.otp, timeout=600)  # 10 min expiry
            return Response({"message": "OTP sent to email"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView):
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        cached_otp = cache.get(f'otp_{email}')
        user = CustomUser.objects.filter(email=email).first()
        if user and cached_otp == otp and user.otp_expiry > timezone.now():
            user.is_email_verified = True
            user.otp = None
            user.otp_expiry = None
            user.save()
            cache.delete(f'otp_{email}')
            return Response({"message": "Email verified"}, status=status.HTTP_200_OK)
        return Response({"error": "Invalid or expired OTP"}, status=status.HTTP_400_BAD_REQUEST)

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