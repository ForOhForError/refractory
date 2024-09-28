from web_interaction.template_parse import Element, TemplateOverwriter
from django.template.loader import render_to_string

def rewrite_element_with_template(input_body:str, django_template_name:str, *search_args, foundry_instance=None, **search_kwargs) -> str:
    parse = TemplateOverwriter()
    parse.feed(input_body)
    formfind = parse.root.search(*search_args, **search_kwargs)
    if len(formfind) == 1:
        join_form = formfind[0]
        django_parse = TemplateOverwriter()
        context = {}
        if foundry_instance:
            context["slug"] = foundry_instance.instance_slug
        django_rendered = render_to_string(django_template_name,context)
        django_parse.feed(django_rendered)
        remaining_elements = join_form.search("h2",{}, limit_depth=0) # header
        remaining_elements.append(django_parse.root)
        join_form.clear()
        for element in remaining_elements:
            join_form.put_child(element)
    recon = parse.reconstructed
    return recon

def make_login_rewrite_rule(*search_args, **search_kwargs):
    def rewrite_rule(input_body, instance):
        return rewrite_element_with_template(input_body, "injected_login_button.html", *search_args, foundry_instance=instance, **search_kwargs)
    return rewrite_rule

def make_setup_rewrite_rule(*search_args, **search_kwargs):
    def rewrite_rule(input_body, instance):
        return rewrite_element_with_template(input_body, "injected_login_button.html", *search_args, foundry_instance=instance, **search_kwargs)
    return rewrite_rule

def make_overwrite_rule(django_template_name:str):
    def overwrite_entirely(_, instance):
        return render_to_string(django_template_name,{"slug":instance.instance_slug})
    return overwrite_entirely

REWRITE_RULES = {
    # Login Button
    "templates/setup/join-game.html": make_login_rewrite_rule("div", {"class":"app"}, limit_matches=1), #v9
    "templates/setup/join-game.hbs": make_login_rewrite_rule("div", {"class":"join-form"}), #v11
    "templates/setup/parts/join-form.hbs": make_overwrite_rule("injected_login_button.html"), #v12
    # Return to Setup
    
}