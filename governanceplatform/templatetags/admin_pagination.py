from django import template
from django.contrib.admin.views.main import PAGE_VAR, ChangeList

register = template.Library()


@register.simple_tag
def admin_pagination(cl: ChangeList, page_range) -> dict:
    """Links and counts for the admin list pagination, laid out like the public one
    (theme parts/pagination.html), which Django's pagination context does not provide."""
    page = cl.paginator.get_page(cl.page_num)

    def url(number: int) -> str:
        return cl.get_query_string({PAGE_VAR: number})

    return {
        "first_url": url(1) if page.has_previous() else None,
        "previous_url": url(page.previous_page_number()) if page.has_previous() else None,
        "next_url": url(page.next_page_number()) if page.has_next() else None,
        "last_url": url(cl.paginator.num_pages) if page.has_next() else None,
        "pages": [
            {
                "number": number,
                "url": None if number == cl.paginator.ELLIPSIS else url(number),
                "current": number == cl.page_num,
            }
            for number in page_range
        ],
        "start": page.start_index(),
        "end": page.end_index(),
    }
