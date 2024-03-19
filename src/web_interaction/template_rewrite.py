from web_interaction.template_parse import Element, TemplateOverwriter
from django.template.loader import render_to_string

def rewrite_login_form(input:str) -> str:
    parse = TemplateOverwriter()
    parse.feed(input)
    formfind = parse.root.search("div", {"class":"join-form"})
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

REWRITE_RULES = {
    "templates/setup/join-game.hbs": rewrite_login_form
}