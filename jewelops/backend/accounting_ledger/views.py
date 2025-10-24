from django.shortcuts import render
from django.conf import settings

def index(request, path=''):
  """
  This view renders the index.html template, which will host our React app.
  """
  if settings.DEBUG:
        print(f"Serving template for path: '{path}'")
        print(f"Template dirs: {settings.TEMPLATES[0]['DIRS']}")
  return render(request, 'index.html')