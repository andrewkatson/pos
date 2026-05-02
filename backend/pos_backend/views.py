from django.http import JsonResponse


def health(request):
    """Health check endpoint that returns an ok  JSON response with status 200."""
    return JsonResponse({"status": "ok"}, status=200)
