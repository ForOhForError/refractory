from web_interaction.template_parse import Element, TemplateOverwriter
from django.template.loader import render_to_string

def rewrite_login_form(input:str, *search_args, **search_kwargs) -> str:
    print("rewriting")
    parse = TemplateOverwriter()
    parse.feed(input)
    formfind = parse.root.search(*search_args, **search_kwargs)
    print(formfind)
    if len(formfind) == 1:
        join_form = formfind[0]
        django_parse = TemplateOverwriter()
        django_rendered = render_to_string("injected_login_button.html")
        django_parse.feed(django_rendered)
        remaining_elements = join_form.search("h2",{}, limit_depth=0) # header
        remaining_elements.append(django_parse.root)
        join_form.clear()
        for element in remaining_elements:
            join_form.put_child(element)
    recon = parse.reconstructed
    return recon

def make_rewrite_rule(*search_args, **search_kwargs):
    def rewrite_rule(input):
        return rewrite_login_form(input, *search_args, **search_kwargs)
    return rewrite_rule

def overwrite_entirely(input):
    return render_to_string("injected_login_button.html")

REWRITE_RULES = {
    "templates/setup/join-game.hbs": make_rewrite_rule("div", {"class":"join-form"}), #v10
    "templates/setup/parts/join-form.hbs": overwrite_entirely, #v11
}