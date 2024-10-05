from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView
from django.urls import reverse_lazy
from django.contrib import messages


# Create your views here.
class RefractoryLoginView(LoginView):
    redirect_authenticated_user = False
    template_name='refractory_login.html'
    
    def form_invalid(self, form):
        messages.error(self.request,'Invalid username or password')
        return self.render_to_response(self.get_context_data(form=form))

class AboutView(TemplateView):
    template_name = "foundry_portal_panels.html"