from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.contrib import messages

from refractory_home.models import FoundryInstance, ManagedFoundryUser
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from django.contrib.admin.views.decorators import staff_member_required

from refractory_home.models import FoundryState

# Create your views here.
class RefractoryLoginView(LoginView):
    redirect_authenticated_user = False
    template_name='refractory_login.html'
    
    def form_invalid(self, form):
        messages.error(self.request,'Invalid username or password')
        return self.render_to_response(self.get_context_data(form=form))

class PanelView(LoginRequiredMixin, TemplateView):
    template_name = "status_panel.html"
    login_url = "/manage/login/"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context["instances"] = FoundryInstance.objects.all()
        return context

@login_required
def login_to_instance(request, instance_slug):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        world_id = instance.get_join_info().get("world", {}).get("id")
        managed_users = ManagedFoundryUser.objects.filter(owner=request.user, instance=instance, world_id=world_id)
        return render(request, "login_to_instance.html", {"users":managed_users, "instance": instance})
    except FoundryInstance.DoesNotExist:
        raise PermissionDenied
    raise PermissionDenied

@login_required
def login_to_instance_as_user(request, instance_slug, user_ix):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        world_id = instance.active_world_id
        managed_users = ManagedFoundryUser.objects.filter(owner=request.user, instance=instance, world_id=world_id)
        if len(managed_users) > user_ix:
            managed_user = managed_users[user_ix]
            redirect_url, cookies = instance.vtt_login(managed_user)
            if redirect_url:
                redirect_res = redirect(redirect_url)
                for key, value in cookies.items():
                    if value:
                        redirect_res.set_cookie(key=key, value=value, samesite='Strict', secure=False)
                return redirect_res
    except FoundryInstance.DoesNotExist:
        raise PermissionDenied
    raise PermissionDenied

@login_required
@staff_member_required
def login_to_instance_as_admin(request, instance_slug):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        if instance.instance_state == FoundryState.JOIN:
            instance.deactivate_world()
        if instance.instance_state == FoundryState.SETUP:
            redirect_url, cookies = instance.admin_login()
            if redirect_url:
                redirect_res = redirect(redirect_url)
                for key, value in cookies.items():
                    if value:
                        redirect_res.set_cookie(key=key, value=value, samesite='Strict', secure=False)
                return redirect_res
        else:
            messages.error(request,'Bad Instance State')
    except FoundryInstance.DoesNotExist:
        messages.error(request,'Bad request')
        return redirect(reverse("panel"))
    return redirect(reverse("panel"))

@login_required
@staff_member_required
def login_to_instance_as_managed_gm(request, instance_slug):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        if instance.instance_state == FoundryState.JOIN:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            managed_users = ManagedFoundryUser.objects.filter(managed_gm=True, instance=instance, world_id=instance.active_world_id)
            if len(managed_users):
                managed_user = managed_users.first()
                redirect_url, cookies = instance.vtt_login(managed_user)
                if redirect_url:
                    redirect_res = redirect(redirect_url)
                    for key, value in cookies.items():
                        if value:
                            redirect_res.set_cookie(key=key, value=value, samesite='Strict', secure=False)
                    return redirect_res
    except FoundryInstance.DoesNotExist:
        raise PermissionDenied
    raise PermissionDenied


@login_required
def activate_world(request, instance_slug, world_id):
    if request.method == "POST":
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            if not instance.is_active:
                activated = instance.activate()
                if not activated:
                    messages.info(request, f"Couldn't launch instance {instance.display_name} to activate world.")
                    return redirect(reverse("panel"))
            world_launched = instance.activate_world(world_id, force=False)
            if world_launched:
                messages.info(request, f"World activated.")
            else:
                messages.info(request, "World could not be activated.")
        except FoundryInstance.DoesNotExist:
            messages.info(request, f"Instance ID Invalid")
    return redirect(reverse("panel"))

@login_required
def activate_instance(request, instance_slug):
    if request.method == "POST":
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            instance.activate()
        except FoundryInstance.DoesNotExist:
            raise PermissionDenied
    messages.info(request, f"Activated instance {instance.display_name}")
    return redirect(reverse("panel"))
