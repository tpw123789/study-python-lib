import functools
import re
import string
import typing as t

if t.TYPE_CHECKING:
    import typing_extensions as te

    class HasHTML(te.Protocol):
        def __html__(self):
            pass

__version__ = '2.1.1'


_strip_comments_re = re.compile(r"<!--.*?-->")  # html註解
_strip_tags_re = re.compile(r"<.*?>")  # html標籤


def _simple_escaping_wrapper(name: str) -> t.Callable[..., 'Markup']:
    """包裝:class:str 的function"""
    orig = getattr(str, name)

    @functools.wraps(orig)
    def wrapped(self: 'Markup', *args: t.Any, **kwargs: t.Any) -> 'Markup':
        args = _escape_argspec(list(args), enumerate(args), self.escape)  # args需轉成list, tuple不是mutable type
        _escape_argspec(kwargs, kwargs.items(), self.escape)
        return self.__class__(orig(self, *args, **kwargs))
    return wrapped


class Markup(str):
    """
    >>> Markup("Hello, <em>World</em>!")
    Markup('Hello, <em>World</em>!')
    >>> Markup(42)
    Markup('42')
    >>> Markup.escape("Hello, <em>World</em>!")
    Markup('Hello, &lt;em&gt;World&lt;/em&gt;!')

    This implements the ``__html__()`` interface that some frameworks
    use. Passing an object that implements ``__html__()`` will wrap the
    output of that method, marking it safe.

    >>> class Foo:
    ...     def __html__(self):
    ...         return '<a href="/foo">foo</a>'
    ...
    >>> Markup(Foo())
    Markup('<a href="/foo">foo</a>')

    This is a subclass of :class:`str`. It has the same methods, but
    escapes their arguments and returns a ``Markup`` instance.

    >>> Markup("<em>%s</em>") % ("foo & bar",)
    Markup('<em>foo &amp; bar</em>')
    >>> Markup("<em>Hello</em> ") + "<foo>"
    Markup('<em>Hello</em> &lt;foo&gt;')
    """
    __slots__ = ()

    def __new__(cls, base: t.Any = '', encoding: t.Optional[str] = None, errors: str = 'strict') -> 'Markup':
        if hasattr(base, '__html__'):
            base = base.__html__()

        if encoding is None:
            return super().__new__(cls, base)

        return super().__new__(cls, base, encoding, errors)

    def __html__(self) -> 'Markup':
        return self

    def __add__(self, other: t.Union[str, 'HasHTML']) -> 'Markup':
        if isinstance(other, str) or hasattr(other, '__html__'):
            return self.__class__(super().__add__(self.escape(other)))
        return NotImplemented

    def __radd__(self, other: t.Union[str, 'HasHTML']) -> 'Markup':
        if isinstance(other, str) or hasattr(other, '__html__'):
            return self.escape(other).__add__(self)
        return NotImplemented

    def __mul__(self, num: 'te.SupportsIndex') -> 'Markup':
        if isinstance(num, int):
            return self.__class__(super().__mul__(num))
        return NotImplemented

    __rmul__ = __mul__

    def __mod__(self, arg: t.Any) -> 'Markup':
        if isinstance(arg, tuple):
            arg = tuple(_MarkupEscapeHelper(x, self.escape) for x in arg)
        elif hasattr(type(arg), '__getitem__') and not isinstance(arg, str):
            arg = _MarkupEscapeHelper(arg, self.escape)
        else:
            arg = (_MarkupEscapeHelper(arg, self.escape),)
        return self.__class__(super().__mod__(arg))

    def __repr__(self):
        return f'{self.__class__.__name__}({super().__repr__()})'

    def join(self, seq: t.Iterable[t.Union[str, 'HasHTML']]) -> 'Markup':
        return self.__class__(super().join(map(self.escape, seq)))

    join.__doc__ = str.join.__doc__

    def split(self, sep: t.Optional[str] = None, maxsplit: int = -1) -> t.List['Markup']:
        return [self.__class__(v) for v in super().split(sep, maxsplit)]

    split.__doc__ = str.split.__doc__

    def rsplit(self, sep: t.Optional[str] = None, maxsplit: int = -1) -> t.List['Markup']:
        return [self.__class__(v) for v in super().rsplit(sep, maxsplit)]

    rsplit.__doc__ = str.rsplit.__doc__

    def splitlines(self, keepends: bool = False) -> t.List['Markup']:
        return [self.__class__(v) for v in super().splitlines(keepends)]

    rsplit.__doc__ = str.rsplit.__doc__

    def unescape(self):
        from html import unescape
        return unescape(str(self))

    def striptags(self) -> str:
        value = _strip_comments_re.sub('', self)
        value = _strip_tags_re.sub('', value)
        value = ' '.join(value.split())  # 去掉換行
        return Markup(value).unescape()

    @classmethod
    def escape(cls, s: t.Any) -> 'Markup':
        rv = escape(s)

        # 確保是:class:Markup類
        if rv.__class__ is not cls:
            return cls(rv)
        return rv

    for method in (
            "__getitem__",
            "capitalize",
            "title",
            "lower",
            "upper",
            "replace",
            "ljust",
            "rjust",
            "lstrip",
            "rstrip",
            "center",
            "strip",
            "translate",
            "expandtabs",
            "swapcase",
            "zfill",
    ):
        locals()[method] = _simple_escaping_wrapper(method)
    del method

    def partition(self, sep: str) -> t.Tuple['Markup', 'Markup', 'Markup']:
        l, s, r = super().partition(self.escape(sep))
        cls = self.__class__
        return cls(l), cls(s), cls(r)

    def rpartition(self, sep: str) -> t.Tuple['Markup', 'Markup', 'Markup']:
        l, s, r = super().rpartition(self.escape(sep))
        cls = self.__class__
        return cls(l), cls(s), cls(r)

    def format(self, *args: t.Any, **kwargs: t.Any) -> 'Markup':
        formatter = EscapeFormatter(self.escape)
        return self.__class__(formatter.vformat(self, args, kwargs))

    def __html_format__(self, format_spec: str) -> 'Markup':
        if format_spec:
            raise ValueError('Unsupported format specification for Markup.')
        return self


class EscapeFormatter(string.Formatter):
    """跳脫格式"""
    __slots__ = ('escape',)

    def __init__(self, escape: t.Callable[[t.Any], Markup]):
        self.escape = escape
        super().__init__()

    def format_field(self, value: t.Any, format_spec: str) -> str:
        if hasattr(value, '__html_format__'):
            rv = value.__html_format__(format_spec)
        elif hasattr(value, '__html__'):
            if format_spec:
                # 若有format_spec需定義'__html_format__'
                raise ValueError(
                    f"Format specifier {format_spec} given, but {type(value)} does not"
                    " define __html_format__. A class that defines __html__ must define"
                    " __html_format__ to work with format specifiers."
                )
            rv = value.__html__()
        else:
            # 使用父類別，Formatter.format_field -> format(value, format_spec: str)
            rv = string.Formatter.format_field(self, value=value, format_spec=str(format_spec))
        return str(self.escape(rv))


_ListOrDict = t.TypeVar('_ListOrDict', list, dict)  # list 或 dict


def _escape_argspec(obj: _ListOrDict, iterable: t.Iterable[t.Any], escape: t.Callable[[t.Any], Markup]):
    """Helper func for string-wrapped functions"""
    for key, value in iterable:
        if isinstance(value, str) or hasattr(value, '__html__'):
            obj[key] = escape(value)
    return obj


class _MarkupEscapeHelper:
    """Markup __mod__ 的 helper class"""
    __slots__ = ('obj', 'escape')

    def __init__(self, obj: t.Any, escape: t.Callable[[t.Any], Markup]) -> None:
        self.obj = obj
        self.escape = escape

    def __getitem__(self, item: t.Any) -> '_MarkupEscapeHelper':
        return _MarkupEscapeHelper(self.obj[item], self.escape)

    def __str__(self) -> str:
        return str(self.escape(self.obj))

    def __repr__(self):
        return str(self.escape(repr(self.obj)))

    def __int__(self):
        return int(self.obj)

    def __float__(self):
        return float(self.obj)


# circular import
try:
    from markupsafe._speedups import escape
    from markupsafe._speedups import escape_silent
    from markupsafe._speedups import soft_str
except ImportError:
    from markupsafe._native import escape
    from markupsafe._native import escape_silent
    from markupsafe._native import soft_str
