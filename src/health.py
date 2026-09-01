from django.http import JsonResponse


def health(request):
    """Minimal process-readiness probe with no credentials or database details."""
    response = JsonResponse({"service": "grand", "status": "ok"})
    response["Cache-Control"] = "no-store"
    return response
