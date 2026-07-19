from functools import cached_property
import logging
import os
import zipfile
from io import BytesIO
from pathlib import Path
from wsgiref.util import FileWrapper

from django import forms
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views import View
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
from django_ratelimit.decorators import ratelimit

from refractory_home.models import (
    FoundryInstance,
    FoundryState,
    FoundryVersion,
    ManagedFoundryUser,
    FoundryInvite,
)
from refractory_home.models.foundry_models import FoundryLicense, FoundryRole
from web_interaction.foundry_interaction import (
    FOUNDRY_USERNAME_COOKIE,
    FOUNDRY_SESSION_COOKIE,
    foundry_site_login,
)

#
# Access Control
#


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class FoundrySiteInteractionRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        if self.request.user.is_superuser:
            foundry_user = self.request.get_signed_cookie(FOUNDRY_USERNAME_COOKIE, None)
            foundry_cookie = self.request.get_signed_cookie(
                FOUNDRY_SESSION_COOKIE, None
            )
            return foundry_user and foundry_cookie
        else:
            return False

    def get_foundry_site_info(self):
        foundry_user = self.request.get_signed_cookie(FOUNDRY_USERNAME_COOKIE, None)
        foundry_session = self.request.get_signed_cookie(FOUNDRY_SESSION_COOKIE, None)
        return (foundry_user, foundry_session)


class FoundryVTTLoginContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            foundry_user = self.request.get_signed_cookie(FOUNDRY_USERNAME_COOKIE)
            context["foundry_user"] = foundry_user
        except KeyError:
            pass
        return context


#
# Helper Classes/Functions
#


def get_confirm_delete_form(
    string_to_match: str = "Good Idea",
    label: str = "Confirm Deletion",
    help_text: str = 'To confirm deletion, enter "Good Idea".',
):
    class ConfirmDeleteForm(forms.Form):
        confirm = forms.CharField(required=True, label=label, help_text=help_text)

        def clean_confirm(self):
            confirm_val = self.cleaned_data.get("confirm")
            if confirm_val != string_to_match:
                raise forms.ValidationError(
                    "Deletion confirmation did not match expected value."
                )
            return confirm_val

    return ConfirmDeleteForm


#
# Task Stuff
#
class TaskStatusView(View):
    def get(self, request, request_id, **kwargs):
        return HttpResponse("DNE")


#
# Front Page
#


class PanelView(LoginRequiredMixin, TemplateView):
    template_name = "status_panel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["instances"] = FoundryInstance.viewable_by_user(self.request.user)
        return context


#
# Version Managment
#


class MajorVersionPaginator(Paginator):
    def page(self, number):
        """Return a Page object for the given 1-based page number."""
        number = self.validate_number(number)
        return self._get_page(
            [
                ver
                for ver in self.object_list
                if ver.major_version == self.major_versions[number - 1]
            ],
            number,
            self,
        )

    @cached_property
    def major_versions(self):
        return sorted(
            list(set([ver.major_version for ver in self.object_list])), reverse=True
        )

    @cached_property
    def num_pages(self):
        return len(self.major_versions)


class VersionListView(SuperuserRequiredMixin, FoundryVTTLoginContextMixin, ListView):
    model = FoundryVersion
    paginator_class = MajorVersionPaginator
    paginate_by = 100
    template_name = "version_list.html"
    ordering = ["version_string"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context

    def get_queryset(self):
        FoundryVersion.load_versions(limit_refresh_seconds=60)
        qs = super().get_queryset()
        return list(reversed(sorted(qs, key=lambda n: (n.version_tuple))))


class DownloadVersion(View, FoundrySiteInteractionRequiredMixin):
    def post(self, request, *args, version_string="", **kwargs):
        try:
            foundry_username, foundry_session_id = self.get_foundry_site_info()
            foundry_version = FoundryVersion.objects.get(version_string=version_string)
            foundry_version.download_version(foundry_session_id)
            messages.info(
                request,
                _("Downloaded Version %s (Build %s) successfully.")
                % (foundry_version.version_string, foundry_version.build),
            )
        except FoundryVersion.DoesNotExist:
            messages.error(request, _("Bad Version String"))
        except Exception as ex:
            raise ex
        return redirect(reverse("version_list"))


#
# License Management
#


class LicenseListView(SuperuserRequiredMixin, ListView):
    model = FoundryLicense
    paginate_by = 20
    template_name = "license_list.html"
    ordering = ["license_name"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context


class LicenseCreateView(SuperuserRequiredMixin, CreateView):
    model = FoundryLicense
    fields = ["license_name", "license_key"]
    template_name = "license_create.html"
    success_url = reverse_lazy("license_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Create Foundry License")
        context["submit_text"] = _("Create")
        return context


class LicenseUpdateView(SuperuserRequiredMixin, UpdateView):
    model = FoundryLicense
    fields = ["license_name"]
    template_name = "license_update.html"
    slug_field = "id"
    slug_url_kwarg = "id"
    success_url = reverse_lazy("license_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Update License")
        context["submit_text"] = _("Update")
        return context


class LicenseDeleteView(SuperuserRequiredMixin, DeleteView):
    model = FoundryLicense
    template_name = "license_delete.html"
    slug_field = "id"
    slug_url_kwarg = "id"
    success_url = reverse_lazy("license_list")
    form_class = forms.Form

    def get_form_class(self):
        return get_confirm_delete_form(
            string_to_match="Remove License",
            help_text="To confirm licence removal, enter 'Remove License'",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Delete Foundry Instance")
        context["submit_text"] = _("Delete")
        return context


class ImportLicenses(View, FoundrySiteInteractionRequiredMixin):
    def post(self, request):
        foundry_user, foundry_session_id = self.get_foundry_site_info()
        FoundryLicense.load_from_foundry_account(foundry_session_id, foundry_user)
        return redirect(reverse("license_list"))


#
# Instance Managment
#


class InstanceCreateView(SuperuserRequiredMixin, CreateView):
    model = FoundryInstance
    fields = [
        "instance_name",
        "instance_slug",
        "display_name",
        "foundry_version",
        "view_group",
        "access_group",
        "gm_group",
        "manage_group",
    ]
    template_name = "instance_create.html"
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
        ).order_by("-build")
        return form


class InstanceUpdateView(SuperuserRequiredMixin, UpdateView):
    model = FoundryInstance
    fields = [
        "instance_name",
        "instance_slug",
        "display_name",
        "foundry_version",
        "view_group",
        "access_group",
        "gm_group",
        "manage_group",
    ]
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
        ).order_by("-build")
        return form


class InstanceDeleteView(SuperuserRequiredMixin, DeleteView):
    model = FoundryInstance
    template_name = "instance_delete.html"
    slug_field = "instance_slug"
    slug_url_kwarg = "instance_slug"
    success_url = reverse_lazy("instance_list")
    form_class = get_confirm_delete_form()

    def get_form_class(self):
        instance = FoundryInstance.objects.get(
            instance_slug=self.kwargs.get("instance_slug")
        )
        return get_confirm_delete_form(
            string_to_match=instance.instance_name,
            label="Confirm Instance Name",
            help_text=f"Enter the instance name, '{instance.instance_name}', to confirm instance deletion.",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Delete Foundry Instance")
        context["submit_text"] = _("Delete")
        return context


class InstanceListView(SuperuserRequiredMixin, ListView):
    model = FoundryInstance
    paginate_by = 20
    template_name = "instance_list.html"
    ordering = ["foundry_version"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context


#
# Login (Refractory and FoundryVTT site)
#


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST"), name="post")
class RefractoryLoginView(LoginView):
    redirect_authenticated_user = False
    template_name = "refractory_login.html"

    def form_invalid(self, form):
        messages.error(self.request, _("Invalid username or password"))
        return self.render_to_response(self.get_context_data(form=form))


class FoundryLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class FoundryLoginFormView(
    SuperuserRequiredMixin, FoundryVTTLoginContextMixin, FormView
):
    template_name = "foundry_login.html"
    form_class = FoundryLoginForm

    def get_success_url(self):
        """Return the default redirect URL."""
        next_page = self.request.GET.get("next")
        if next_page:
            return resolve_url(next_page)
        else:
            return reverse_lazy("panel")

    def form_valid(self, form):
        resp = super().form_valid(form)
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        foundry_site_login(username, password, resp)
        return resp


#
# Group Management
#


class GroupRelatedUserForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]

    users = forms.ModelMultipleChoiceField(
        queryset=get_user_model().objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        if kwargs.get("instance"):
            initial = kwargs.setdefault("initial", {})
            initial["users"] = [t.pk for t in kwargs["instance"].user_set.all()]
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        old_save_m2m = self.save_m2m

        def save_m2m():
            old_save_m2m()
            instance.user_set.clear()
            instance.user_set.add(*self.cleaned_data["users"])

        self.save_m2m = save_m2m

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class GroupListView(SuperuserRequiredMixin, ListView):
    model = Group
    paginate_by = 20
    template_name = "group_list.html"
    ordering = ["id"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context


class GroupCreateView(SuperuserRequiredMixin, CreateView):
    model = Group
    fields = ["name"]
    template_name = "group_create.html"
    success_url = reverse_lazy("group_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Create Foundry Instance")
        context["submit_text"] = _("Create")
        return context


class GroupUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Group
    template_name = "group_update.html"
    slug_field = "id"
    slug_url_kwarg = "group_id"
    form_class = GroupRelatedUserForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Update Foundry Instance")
        context["submit_text"] = _("Update")
        return context

    def get_success_url(self):
        if "group_id" in self.kwargs:
            group_id = self.kwargs["group_id"]
            return reverse("group_update", kwargs={"group_id": group_id})
        else:
            return reverse("panel")


#
# Invite Management
#


class InviteListView(SuperuserRequiredMixin, ListView):
    model = FoundryInvite
    paginate_by = 20
    template_name = "invite_list.html"
    ordering = ["id"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        return context


class InviteCreateView(SuperuserRequiredMixin, CreateView):
    model = FoundryInvite
    fields = ["invite_name", "uses", "assign_user_groups"]
    template_name = "invite_create.html"
    success_url = reverse_lazy("invite_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Create Invite")
        context["submit_text"] = _("Create")
        return context


class InviteUpdateView(SuperuserRequiredMixin, UpdateView):
    model = FoundryInvite
    template_name = "invite_update.html"
    slug_field = "id"
    slug_url_kwarg = "id"
    fields = ["invite_name", "invite_code", "uses", "assign_user_groups"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Update Invite")
        context["submit_text"] = _("Update")
        return context

    def get_success_url(self):
        if "invite_id" in self.kwargs:
            invite_id = self.kwargs["invite_id"]
            return reverse("invite_update", kwargs={"group_id": invite_id})
        else:
            return reverse("panel")


class InviteDeleteView(SuperuserRequiredMixin, DeleteView):
    model = FoundryInvite
    template_name = "invite_delete.html"
    slug_field = "id"
    slug_url_kwarg = "id"
    success_url = reverse_lazy("invite_list")
    form_class = get_confirm_delete_form()

    def get_form_class(self):
        return get_confirm_delete_form()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Delete Invite")
        context["submit_text"] = _("Delete")
        return context


#
# Signup
#


class InviteCodeUserCreationForm(UserCreationForm):
    invite_code = forms.CharField(help_text="Invite Code")

    def clean_invite_code(self):
        invite_code = self.cleaned_data.get("invite_code")
        if invite_code:
            try:
                invite = FoundryInvite.objects.get(invite_code=invite_code)
            except FoundryInvite.DoesNotExist:
                raise forms.ValidationError("Invite invalid")
        else:
            raise forms.ValidationError("Invite code required")
        return invite_code

    def save(self, commit=True):
        invite_code = self.cleaned_data.get("invite_code")
        invite = FoundryInvite.objects.get(invite_code=invite_code)
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            for group in invite.assign_user_groups.all():
                user.groups.add(group)
            invite.use_invite()
        return user


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST"), name="post")
class SignupFormView(FormView):
    template_name = "signup.html"
    form_class = InviteCodeUserCreationForm
    success_url = reverse_lazy("panel")

    def form_valid(self, form) -> HttpResponse:
        form.save()
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.GET:
            kwargs["initial"] = {"invite_code": self.request.GET.get("code", "")}
        return kwargs

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return super().post(request, *args, **kwargs)


#
# Actions for Instances
#


class DownloadInstanceBackup(View, SuperuserRequiredMixin):
    def post(self, request, *args, instance_slug="", **kwargs):
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


class ManagedUserCreationForm(forms.Form):
    user_name = forms.CharField(label="Username", max_length=255)
    is_gm = forms.BooleanField(label="Register as GM", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = None

    def is_valid(self) -> bool:
        valid = self.instance != None and self.instance.active_world_id != None
        return super().is_valid() if valid else False

    def save(self, commit=True):
        if self.instance:
            world_id = self.instance.active_world_id
        else:
            world_id = None
        user = ManagedFoundryUser(
            user_name=self.cleaned_data.get("user_name"),
            user_id="a",
            initial_role=FoundryRole.GM
            if self.cleaned_data.get("is_gm")
            else FoundryRole.PLAYER,
            instance=self.instance,
            world_id=world_id,
        )
        if commit:
            user.save()
        return user


class RegisterUserView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    model = ManagedFoundryUser
    form_class = ManagedUserCreationForm
    template_name = "register_user.html"

    def get_success_url(self) -> str:
        instance = self.get_instance()
        if instance:
            return reverse_lazy("vtt_choose_user", args=[instance.instance_slug])
        else:
            return reverse_lazy("panel")

    def get_instance(self):
        try:
            return FoundryInstance.objects.get(
                instance_slug=self.kwargs.get("instance_slug")
            )
        except FoundryInstance.DoesNotExist:
            return None

    def test_func(self):
        instance = self.get_instance()
        if instance:
            return instance.user_can_register(
                self.request.user
            ) or instance.user_can_register_gms(self.request.user)
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        context["header_text"] = _("Register Player")
        context["submit_text"] = _("Register")
        context["instance"] = self.get_instance()
        context["user"] = self.request.user
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_form(self):
        form = super().get_form()
        try:
            form.instance = FoundryInstance.objects.get(
                instance_slug=self.kwargs.get("instance_slug")
            )  # type: ignore
            form.fields["is_gm"].disabled = not form.instance.user_can_register_gms(
                self.request.user
            )  # type: ignore
        except FoundryInstance.DoesNotExist:
            pass
        return form


class InstanceLoginView(LoginRequiredMixin, View):
    def get(self, request, *args, instance_slug="", **kwargs):
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


class ConfirmSetupView(LoginRequiredMixin, TemplateView):
    template_name = "setup_confirm.html"

    def get_instance(self):
        try:
            return FoundryInstance.objects.get(
                instance_slug=self.kwargs.get("instance_slug")
            )
        except FoundryInstance.DoesNotExist:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context["instance"] = self.get_instance()
        return context


class InstanceUserLogin(LoginRequiredMixin, View):
    def post(self, request, *args, instance_slug="", user_ix=0, **kwargs):
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
                    if cookies:
                        for key, value in cookies.items():
                            if value:
                                redirect_res.set_cookie(
                                    key=key,
                                    value=value,
                                    samesite="Strict",
                                    secure=False,
                                )
                        return redirect_res
        except FoundryInstance.DoesNotExist:
            messages.error(request, _("Instance does not exist."))
            return redirect(reverse("panel"))
        messages.error(request, _("Login failed."))
        return redirect(reverse("panel"))


class InstanceSetupLogin(LoginRequiredMixin, View):
    def post(self, request, *args, instance_slug="", **kwargs):
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            if instance.user_can_manage(request.user):
                if instance.instance_state == FoundryState.JOIN:
                    instance.deactivate_world()
                if instance.instance_state == FoundryState.SETUP:
                    redirect_url, cookies = instance.admin_login()
                    if redirect_url:
                        redirect_res = redirect(redirect_url)
                        if cookies:
                            for key, value in cookies.items():
                                if value:
                                    redirect_res.set_cookie(
                                        key=key,
                                        value=value,
                                        samesite="Strict",
                                        secure=False,
                                    )
                            return redirect_res
                else:
                    messages.error(request, _("Bad Instance State"))
            else:
                return redirect(
                    reverse("confirm_instance_setup", args=[instance.instance_slug])
                )
        except FoundryInstance.DoesNotExist:
            messages.error(request, _("Instance does not exist."))
            return redirect(reverse("panel"))
        messages.error(request, _("Login failed."))
        return redirect(reverse("panel"))


class InstanceManagedGMLogin(SuperuserRequiredMixin, View):
    def post(self, request, *args, instance_slug="", **kwargs):
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            if instance.instance_state == FoundryState.JOIN:
                instance = FoundryInstance.objects.get(instance_slug=instance_slug)
                managed_users = ManagedFoundryUser.objects.filter(
                    managed_gm=True,
                    instance=instance,
                    world_id=instance.active_world_id,
                )
                if len(managed_users):
                    managed_user = managed_users.first()
                    redirect_url, cookies = instance.vtt_login(managed_user)
                    if redirect_url:
                        redirect_res = redirect(redirect_url)
                        if cookies:
                            for key, value in cookies.items():
                                if value:
                                    redirect_res.set_cookie(
                                        key=key,
                                        value=value,
                                        samesite="Strict",
                                        secure=False,
                                    )
                            return redirect_res
        except FoundryInstance.DoesNotExist:
            messages.error(request, _("Instance does not exist."))
            return redirect(reverse("panel"))
        messages.error(request, _("Login failed."))
        return redirect(reverse("panel"))


def instrument_url_with_params(url, params):
    if params:
        return f"{url}?{urlencode(params)}"
    else:
        return url


class ActivateWorld(LoginRequiredMixin, View):
    def post(self, request, *args, instance_slug="", world_id="", **kwargs):
        params = None
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            task_id = instance.queue_world_activate(world_id)
            messages.info(request, _("Activating World."))
            params = {"task_id": task_id}
        except FoundryInstance.DoesNotExist:
            messages.error(request, _("Instance does not exist."))
        redir_url = instrument_url_with_params(reverse("panel"), params=params)
        return redirect(redir_url)


class ActivateInstance(LoginRequiredMixin, View):
    def post(self, request, *args, instance_slug="", **kwargs):
        params = None
        try:
            instance = FoundryInstance.objects.get(instance_slug=instance_slug)
            task_id = instance.queue_instance_activate()
            params = {"task_id": task_id}
        except FoundryInstance.DoesNotExist:
            raise PermissionDenied
        messages.info(
            request,
            _("Activated instance %(instance_name)s")
            % {"instance_name": instance.display_name},
        )
        redir_url = instrument_url_with_params(reverse("panel"), params=params)
        return redirect(redir_url)
