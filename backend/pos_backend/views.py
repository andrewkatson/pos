from django.http import JsonResponse


def health(request):
    """Health check endpoint that returns an empty JSON response with status 200."""
    return JsonResponse({}, status=200)
