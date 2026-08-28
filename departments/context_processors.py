from .services.internal_howtos import visible_internal_how_tos


def internal_howtos(request):
    route_name = getattr(getattr(request, "resolver_match", None), "view_name", "") or ""
    department, guides = visible_internal_how_tos(request.user, route_name)
    return {
        "internal_howto_department": department,
        "internal_howtos": guides,
        "internal_howto_route_name": route_name,
    }
