from django.core.paginator import Paginator


def register_page(queryset, request, parameter, anchor):
    """Page an already scoped, deterministically ordered Treasury register."""
    page = Paginator(queryset, 50).get_page(request.GET.get(parameter))
    params = request.GET.copy()
    for name, number in (("previous_url", page.number - 1), ("next_url", page.number + 1)):
        params[parameter] = number
        setattr(page, name, "?" + params.urlencode() + "#" + anchor)
    return page
