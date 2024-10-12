from django import template

register = template.Library()

@register.filter(name='addclass')
def addclass(value, arg):
    try:
        return value.as_widget(attrs={'class': arg})
    except Exception:
        return value