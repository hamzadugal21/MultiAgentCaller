from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    response = HttpResponse("ok\n", content_type="text/plain; charset=utf-8")
    response.headers["Cache-Control"] = "no-store"
    return response
