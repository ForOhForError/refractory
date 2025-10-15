from django import template
from refractory_home.models import FoundryInstance

register = template.Library()


@register.filter(name="can_access")
def can_access(user, instance):
    return instance.user_can_register(user)


@register.filter(name="can_manage")
def can_manage(user, instance):
    return instance.user_can_manage(user)
