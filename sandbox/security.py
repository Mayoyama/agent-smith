"""Restrictions applied to code running in the sandbox worker."""
from common import SandboxConfig
from typing import Any, Mapping, Sequence, NoReturn
from types import ModuleType
import builtins
import socket
import os


BUILTINS_WHITELIST: list[str] = [
    # output and conversions
    "print", "repr", "str", "int", "float", "bool", "complex",
    "chr", "ord", "hex", "bin", "oct", "format", "memoryview",

    # iterables and containers
    "list", "dict", "set", "frozenset", "tuple", "map", "bytes", "bytearray",

    # iteration
    "range", "enumerate", "zip", "filter", "reversed", "sorted", "iter",
    "next", "all", "any", "slice",

    # numbers
    "abs", "min", "max", "sum", "round", "pow", "divmod", "len", "hash",

    # types and classes
    "isinstance", "issubclass", "type", "object", "super", "property",
    "staticmethod", "classmethod", "hasattr", "callable", "id",

    # other
    "NotImplemented", "Ellipsis", "__build_class__", "dir",
]


class Security:
    """Holds the sandbox allowlists and the restricted builtins.

    Attributes:
        allow_imports: Allowed module names; an entry ending in ".*"
            also allows that module's submodules.
        allowed_dirs: Directories sandboxed code may access.
    """

    def __init__(self, config: SandboxConfig):
        """Store the allowlists from the config.

        Args:
            config: Sandbox config with the import and directory
                allowlists.
        """

        self.allow_imports = config.authorized_imports
        self.allowed_dirs = config.allowed_directories
        self.resolved_dirs = [os.path.realpath(d) for d in self.allowed_dirs]

    def safe_import(
            self,
            name: str,
            globals: Mapping[str, Any] | None = None,
            locals: Mapping[str, Any] | None = None,
            fromlist: Sequence[str] | None = None,
            level: int = 0
            ) -> ModuleType:
        """Import a module if it is on the allowlist.

        Replaces __import__ for sandboxed code. Submodules named in
        fromlist are checked against the allowlist as well.

        Args:
            name: Module name being imported.
            globals: Globals of the importing code.
            locals: Locals of the importing code.
            fromlist: Names from a "from x import ..." statement, or
                None for a plain import.
            level: 0 for absolute imports, higher for relative ones.

        Returns:
            The imported module.

        Raises:
            ImportError: If the import is relative or the module or a
                submodule in fromlist is not allowed.
        """

        if level > 0:
            raise ImportError("relative imports are not allowed")

        if not self.is_allowed(name):
            raise ImportError(f"import '{name}' not allowed or not on "
                              "whitelist")

        if fromlist is None:
            fromlist = ()

        module = builtins.__import__(name, globals, locals, fromlist, level)

        for item in fromlist:
            attribute = getattr(module, item, None)

            if isinstance(attribute, ModuleType):
                full_name = f"{name}.{item}"

                if not self.is_allowed(full_name):
                    raise ImportError(f"import '{full_name}' not allowed or "
                                      "not on whitelist")

        return module

    def is_allowed(self, name: str) -> bool:
        """Check a module name against the import allowlist.

        Args:
            name: Full dotted module name.

        Returns:
            True if the name is listed exactly, or falls under an
            entry ending in ".*".
        """

        for allowed in self.allow_imports:
            if allowed == name:
                return True

            if allowed.endswith(".*"):
                basename = allowed.removesuffix("*")

                if name.startswith(basename):
                    return True

        return False

    def build_builtins_whitelist(self) -> dict[str, Any]:
        safe_to_use: dict[str, Any] = {}

        for name in BUILTINS_WHITELIST:
            safe_to_use[name] = getattr(builtins, name)

        for name in dir(builtins):
            value = getattr(builtins, name)

            if isinstance(value, type) and issubclass(value, BaseException):
                if name in ("SystemExit", "KeyboardInterrupt"):
                    continue

                safe_to_use[name] = value

        safe_to_use["__import__"] = self.safe_import
        safe_to_use["open"] = self.open_file

        return safe_to_use

    @staticmethod
    def handle_socket(*args: Any, **kwargs: Any) -> NoReturn:
        raise PermissionError("network access not allowed")

    def replace_socket(self) -> None:
        setattr(socket, "socket", self.handle_socket)
        setattr(socket, "getaddrinfo", self.handle_socket)

    def open_file(self, path: str, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(path, str):
            raise PermissionError("only file paths are allowed")

        real_path = os.path.realpath(path)

        for allowed_dir in self.resolved_dirs:
            if (allowed_dir == real_path
                    or real_path.startswith(allowed_dir + os.sep)):
                return builtins.open(real_path, *args, **kwargs)

        raise PermissionError(f"access to {path} is not allowed")
