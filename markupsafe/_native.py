import typing as t

from . import Markup


def escape(s: t.Any) -> 'Markup':
    """跳脫html的一些特殊字元，並封裝在:class:Markup"""
    if hasattr(s, '__html__'):
        return Markup(s.__html__)

    return Markup(
        str(s)
        .replace("&", "&amp;")
        .replace(">", "&gt;")
        .replace("<", "&lt;")
        .replace("'", "&#39;")
        .replace('"', "&#34;")
    )


def escape_silent(s: t.Optional[t.Any]) -> Markup:
    """一樣回傳Markup類，把None當成空字串"""
    if s is None:
        return Markup()
    return escape(s)


def soft_str(s: t.Any) -> str:
    if not isinstance(s, str):
        return str(s)
    return s

