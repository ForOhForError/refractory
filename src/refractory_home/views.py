import os
import zipfile
from io import BytesIO
from pathlib import Path
from wsgiref.util import FileWrapper

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.views.generic.edit import FormView

from refractory_home.models import (
    FoundryInstance,
    FoundryState,
    FoundryVersion,
    ManagedFoundryUser,
)
from web_interaction.foundry_interaction import (
    FOUNDRY_USERNAME_COOKIE,
    foundry_site_login,
)


class InstanceCreateView(CreateView):
    model = FoundryInstance
    fields = ["instance_name", "instance_slug", "display_name", "foundry_version"]
    template_name = "instance_update.html"
    success_url = reverse_lazy("instance_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Create Foundry Instance")
        context["submit_text"] = _("Create")
        return context

    def get_form(self):
        form = super().get_form()
        form.fields["foundry_version"].queryset = FoundryVersion.objects.filter(
            download_status=FoundryVersion.DownloadStatus.DOWNLOADED
        )
        return form


class InstanceUpdateView(UpdateView):
    model = FoundryInstance
    fields = ["instance_name", "instance_slug", "display_name", "foundry_version"]
    template_name = "instance_update.html"
    slug_field = "instance_slug"
    slug_url_kwarg = "instance_slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Update Foundry Instance")
        context["submit_text"] = _("Update")
        return context

    def get_form(self):
        form = super().get_form()
        form.fields["foundry_version"].queryset = FoundryVersion.objects.filter(
            download_status=FoundryVersion.DownloadStatus.DOWNLOADED
        )
        return form


class InstanceDeleteView(DeleteView):
    model = FoundryInstance
    template_name = "instance_update.html"
    slug_field = "instance_slug"
    slug_url_kwarg = "instance_slug"
    success_url = reverse_lazy("instance_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Delete Foundry Instance")
        context["submit_text"] = _("Delete")
        return context


class InstanceListView(ListView):
    model = FoundryInstance
    paginate_by = 20
    template_name = "instance_list.html"
    ordering = ["foundry_version"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context


class RefractoryLoginView(LoginView):
    redirect_authenticated_user = False
    template_name = "refractory_login.html"

    def form_invalid(self, form):
        messages.error(self.request, _("Invalid username or password"))
        return self.render_to_response(self.get_context_data(form=form))


class PanelView(LoginRequiredMixin, TemplateView):
    template_name = "status_panel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context["instances"] = FoundryInstance.objects.all()
        return context


class FoundryLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class FoundryLoginFormView(FormView, UserPassesTestMixin):
    template_name = "foundry_login.html"
    form_class = FoundryLoginForm
    success_url = reverse_lazy("admin:index")
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        """Use this to add extra context."""
        context = super().get_context_data(**kwargs)
        try:
            foundry_user = self.request.get_signed_cookie(FOUNDRY_USERNAME_COOKIE)
            context["foundry_user"] = foundry_user
        except KeyError:
            pass
        return context

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        resp = super().form_valid(form)
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        foundry_site_login(username, password, resp)
        return resp


@login_required
@staff_member_required
@require_POST
def download_instance_backup(request, instance_slug):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        buf = BytesIO()

        archive = zipfile.ZipFile(buf, "w")
        with buf:
            whitelist_path = Path(os.path.join(instance.data_path, "Data"))
            for root, dirs, files in os.walk(instance.data_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if whitelist_path in Path(file_path).parents:
                        archive.write(file_path, os.path.relpath(file_path))
            archive.close()
            resp = HttpResponse(
                buf.getvalue(), content_type="application/x-zip-compressed"
            )
            resp["Content-Disposition"] = (
                "attachment; filename=refractory_backup_%s.zip" % instance_slug
            )
            return resp
    except FoundryInstance.DoesNotExist:
        messages.error(request, _("Instance does not exist."))
        return redirect(reverse("panel"))
    messages.error(request, _("Download failed."))
    return redirect(reverse("panel"))


@login_required
def login_to_instance(request, instance_slug):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        world_id = instance.get_join_info(sync=True).get("world", {}).get("id")
        managed_users = ManagedFoundryUser.objects.filter(
            owner=request.user, instance=instance, world_id=world_id
        )
        return render(
            request,
            "login_to_instance.html",
            {"users": managed_users, "instance": instance},
        )
    except FoundryInstance.DoesNotExist:
        messages.error(request, _("Instance does not exist."))
        return redirect(reverse("panel"))
    messages.error(request, _("Login failed."))
    return redirect(reverse("panel"))


@login_required
@require_POST
def login_to_instance_as_user(request, instance_slug, user_ix):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        world_id = instance.active_world_id
        managed_users = ManagedFoundryUser.objects.filter(
            owner=request.user, instance=instance, world_id=world_id
        )
        if len(managed_users) > user_ix:
            managed_user = managed_users[user_ix]
            redirect_url, cookies = instance.vtt_login(managed_user)
            if redirect_url:
                redirect_res = redirect(redirect_url)
                for key, value in cookies.items():
                    if value:
                        redirect_res.set_cookie(
                            key=key, value=value, samesite="Strict", secure=False
                        )
                return redirect_res
    except FoundryInstance.DoesNotExist:
        messages.error(request, _("Instance does not exist."))
        return redirect(reverse("panel"))
    messages.error(request, _("Login failed."))
    return redirect(reverse("panel"))


@login_required
@staff_member_required
@require_POST
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
                        redirect_res.set_cookie(
                            key=key, value=value, samesite="Strict", secure=False
                        )
                return redirect_res
        else:
            messages.error(request, _("Bad Instance State"))
    except FoundryInstance.DoesNotExist:
        messages.error(request, _("Instance does not exist."))
        return redirect(reverse("panel"))
    messages.error(request, _("Login failed."))
    return redirect(reverse("panel"))


@login_required
@staff_member_required
@require_POST
def login_to_instance_as_managed_gm(request, instance_slug):
    try:
        instance = FoundryInstance.objects.get(instance_slug=instance_slug)
        if instance.instance_state == FoundryState.JOIN:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            managed_users = ManagedFoundryUser.objects.filter(
                managed_gm=True, instance=instance, world_id=instance.active_world_id
            )
            if len(managed_users):
                managed_user = managed_users.first()
                redirect_url, cookies = instance.vtt_login(managed_user)
                if redirect_url:
                    redirect_res = redirect(redirect_url)
                    for key, value in cookies.items():
                        if value:
                            redirect_res.set_cookie(
                                key=key, value=value, samesite="Strict", secure=False
                            )
                    return redirect_res
    except FoundryInstance.DoesNotExist:
        messages.error(request, _("Instance does not exist."))
        return redirect(reverse("panel"))
    messages.error(request, _("Login failed."))
    return redirect(reverse("panel"))


@login_required
@require_POST
def activate_world(request, instance_slug, world_id):
    if request.method == "POST":
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            if not instance.is_active:
                activated = instance.activate()
                if not activated:
                    messages.info(
                        request,
                        f"Couldn't launch instance {instance.display_name} to activate world.",
                    )
                    return redirect(reverse("panel"))
            world_launched = instance.activate_world(world_id, force=False)
            if world_launched:
                messages.info(request, _("World activated."))
            else:
                messages.info(request, _("World could not be activated."))
        except FoundryInstance.DoesNotExist:
            messages.error(request, _("Instance does not exist."))
    return redirect(reverse("panel"))


@login_required
@require_POST
def activate_instance(request, instance_slug):
    if request.method == "POST":
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            instance.activate()
        except FoundryInstance.DoesNotExist:
            raise PermissionDenied
    messages.info(
        request,
        _("Activated instance %(instance_name)s")
        % {"instance_name": instance.display_name},
    )
    return redirect(reverse("panel"))
