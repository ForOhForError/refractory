from django.template.loader import render_to_string
from socketio.packet import Packet

from web_interaction.template_parse import Element, TemplateOverwriter


def rewrite_template_payload(payload, instance, response_to=None):
    if response_to and response_to.data and isinstance(response_to.data, list):
        verb = response_to.data[0] if len(response_to.data) > 0 else None
        subject = response_to.data[1] if len(response_to.data) > 1 else None
        if verb == "template":
            if payload.data:
                if isinstance(payload.data, list) and len(payload.data) > 0:
                    first_data = payload.data[0]
                    if isinstance(first_data, dict):
                        text_payload = first_data.get("html")
                        success = first_data.get("success")
                        if text_payload:
                            if subject in REWRITE_RULES:
                                rewritten_html = REWRITE_RULES[subject](
                                    text_payload, instance
                                )
                                return Packet(
                                    packet_type=payload.packet_type,
                                    data=[{"html": rewritten_html, "success": success}],
                                    namespace=payload.namespace,
                                    id=payload.id,
                                )
        elif verb == "world":
            if payload.data:
                if isinstance(payload.data, list) and len(payload.data) > 0:
                    first_data = payload.data[0]
                    if isinstance(first_data, dict):
                        addresses = first_data.get("addresses")
                        if addresses:
                            addresses["local"] = instance.amend_invite_url(
                                addresses.get("local", "")
                            )
                            addresses["remote"] = instance.amend_invite_url(
                                addresses.get("remote", "")
                            )
                    return Packet(
                        packet_type=payload.packet_type,
                        data=[first_data],
                        namespace=payload.namespace,
                        id=payload.id,
                    )
    return payload


def rewrite_element_with_template(
    input_body: str,
    django_template_name: str,
    *search_args,
    foundry_instance=None,
    **search_kwargs,
) -> str:
    parse = TemplateOverwriter()
    parse.feed(input_body)
    formfind = parse.root.search(*search_args, **search_kwargs)
    if len(formfind) == 1:
        join_form = formfind[0]
        django_parse = TemplateOverwriter()
        context = {}
        if foundry_instance:
            context["instance"] = foundry_instance
        django_rendered = render_to_string(django_template_name, context)
        django_parse.feed(django_rendered)
        remaining_elements = join_form.search("h2", {}, limit_depth=0)  # header
        remaining_elements.append(django_parse.root)
        join_form.clear()
        for element in remaining_elements:
            join_form.put_child(element)
    recon = parse.reconstructed
    return recon


def make_login_rewrite_rule(*search_args, **search_kwargs):
    def rewrite_rule(input_body, instance):
        return rewrite_element_with_template(
            input_body,
            "injected_login_button.html",
            *search_args,
            foundry_instance=instance,
            **search_kwargs,
        )

    return rewrite_rule


def make_setup_rewrite_rule(*search_args, **search_kwargs):
    def rewrite_rule(input_body, instance):
        return rewrite_element_with_template(
            input_body,
            "injected_admin_login.html",
            *search_args,
            foundry_instance=instance,
            **search_kwargs,
        )

    return rewrite_rule


def make_overwrite_rule(django_template_name: str):
    def overwrite_entirely(_, instance):
        return render_to_string(django_template_name, {"instance": instance})

    return overwrite_entirely


REWRITE_RULES = {
    # Login Button
    "templates/setup/join-game.html": make_login_rewrite_rule(
        "div", {"class": "app"}, limit_matches=1
    ),  # v8-10
    "templates/setup/join-game.hbs": make_login_rewrite_rule(
        "div", {"class": "join-form"}
    ),  # v11
    "templates/setup/parts/join-form.hbs": make_overwrite_rule(
        "injected_login_button.html"
    ),  # v12+
    # Admin Auth
    "templates/setup/join-setup.html": make_setup_rewrite_rule(
        "div", {"class": "join-form"}
    ),  # v11
    "templates/setup/parts/join-setup.hbs": make_overwrite_rule(
        "injected_admin_login.html"
    ),  # v12
}
