from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


class SalesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # Print request data to console
        print("=" * 50)
        print("SALES REQUEST RECEIVED")
        print(f"User: {request.user}")
        print(f"Data: {request.data}")
        print(f"Headers: {request.headers}")
        print("=" * 50)
        
        # Return success response
        return Response({
            "message": "Sales data received successfully!",
            "received_data": request.data,
            "user": str(request.user)
        }, status=status.HTTP_200_OK)