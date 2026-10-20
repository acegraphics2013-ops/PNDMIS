import json

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    request = context.get('request')
    if not request:
        return ''
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == '':
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()


@register.filter
def json_pretty(value):
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


@register.filter
def badge_class(value):
    return {
        'approved': 'b-ok',
        'verified': 'b-info',
        'submitted': 'b-info',
        'review': 'b-soon',
        'pending': 'b-done',
        'returned': 'b-overdue',
        'archived': 'b-done',
        'progress': 'b-info',
        'completed': 'b-ok',
        'validated': 'b-ok',
        'planned': 'b-done',
        'attended': 'b-info',
        'critical': 'b-overdue',
        'high': 'b-soon',
        'normal': 'b-done',
        'day': 'b-info',
        'night': 'b-done',
    }.get(str(value), 'b-info')


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key, '')
    except AttributeError:
        return ''


@register.filter
def percent_of(value, total):
    try:
        total = float(total)
        return f'{(float(value) / total * 100):.0f}%' if total else '—'
    except (TypeError, ValueError):
        return '—'
