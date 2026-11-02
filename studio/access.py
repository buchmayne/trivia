"""Keep the experimental studio unavailable outside authorized local development."""

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseForbidden


def studio_required(view):
    @wraps(view)
    def protected(request, *args, **kwargs):
        # Check at request time as well as at URL registration time.
        if not settings.DEBUG or not settings.ENABLE_V2_STUDIO:
            raise Http404
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (
            request.user.is_staff
            or getattr(getattr(request.user, "profile", None), "is_game_admin", False)
        ):
            return HttpResponseForbidden("Studio author access required.")
        return view(request, *args, **kwargs)

    return protected
