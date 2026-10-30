"""Restrictions applied to code running in the sandbox's child process."""

from common import SandboxConfig
from typing import Any, Mapping, Sequence, NoReturn
from types import ModuleType
import importlib
import builtins
import socket
import ast
import sys
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


DUNDERS_WHITELIST: list[str] = [
    "__init__", "__name__", "__doc__", "__str__", "__repr__",
]


ATTRIBUTE_BLACKLIST: list[str] = [
    "f_back", "f_globals", "f_locals", "f_builtins", "f_code",
    "gi_frame", "gi_code", "cr_frame", "ag_frame",
    "tb_frame", "tb_next", "sys", "modules",
]


class Security:
    """Holds the sandbox allowlists and the restricted builtins.

    Attributes:
        allow_imports: Allowed module names; an entry ending in ".*" also
            allows that module's submodules.
        module_escapes: Attribute names on allowed modules that point to
            modules outside the allowlist (e.g. "_os", "sys").
        allowed_dirs: Directories sandboxed code may access.
        resolved_dirs: The allowed directories with symlinks and ".." resolved.
    """

    def __init__(self, config: SandboxConfig):
        """Store the allowlists and find the module escapes.

        Args:
            config: Sandbox config with the import and directory allowlists.
        """

        self.allow_imports = config.authorized_imports
        self.module_escapes = self._lockdown_module_escapes()

        self.allowed_dirs = config.allowed_directories
        self.resolved_dirs = [os.path.realpath(d) for d in self.allowed_dirs]

    def safe_import(
        self,
        name: str,
        globals: Mapping[str, Any] | None = None,
        locals: Mapping[str, Any] | None = None,
        fromlist: Sequence[str] | None = None,
        level: int = 0,
    ) -> ModuleType:
        """Import a module if it is on the allowlist.

        Replaces __import__ for sandboxed code. Submodules named in fromlist
        are checked against the allowlist as well.

        Args:
            name: Module name being imported.
            globals: Globals of the importing code.
            locals: Locals of the importing code.
            fromlist: Names from a "from x import ..." statement, or None for a
                plain import.
            level: 0 for absolute imports, higher for relative ones.

        Returns:
            The imported module.

        Raises:
            ImportError: If the import is relative or the module or a submodule
                in fromlist is not allowed.
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
            True if the name is listed exactly, or falls under an entry ending
            in ".*".
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
        """Build the restricted builtins for the sandbox namespace.

        Contains the names in BUILTINS_WHITELIST, every exception class except
        SystemExit and KeyboardInterrupt, and the restricted __import__ and
        open.

        Returns:
            Dict to use as the namespace's __builtins__.
        """

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
        """Replacement for socket functions that always refuses.

        Args:
            *args: Ignored.
            **kwargs: Ignored.

        Raises:
            PermissionError: Always.
        """

        raise PermissionError("network access not allowed")

    def replace_socket(self) -> None:
        """Block network access in this process.

        Replaces socket.socket and socket.getaddrinfo with handle_socket.
        Affects the whole process, so it is only called in the child.
        """

        setattr(socket, "socket", self.handle_socket)
        setattr(socket, "getaddrinfo", self.handle_socket)

    def open_file(self, path: str, *args: Any, **kwargs: Any) -> Any:
        """Open a file if it lies inside an allowed directory.

        Replaces open for sandboxed code. The path is resolved first, so
        symlinks and ".." cannot leave the allowed directories.

        Args:
            path: Path of the file to open.
            *args: Passed on to the real open.
            **kwargs: Passed on to the real open.

        Returns:
            The opened file object.

        Raises:
            PermissionError: If path is not a string or resolves to a location
                outside the allowed directories.
        """

        if not isinstance(path, str):
            raise PermissionError("only file paths are allowed")

        real_path = os.path.realpath(path)

        for allowed_dir in self.resolved_dirs:
            if (allowed_dir == real_path
                    or real_path.startswith(allowed_dir + os.sep)):
                return builtins.open(real_path, *args, **kwargs)

        raise PermissionError(f"access to {path} is not allowed")

    def ast_parse(self, code: str) -> None:
        """Reject code that accesses blocked names or attributes.

        Blocks dunder names other than __name__, dunder attributes not in
        DUNDERS_WHITELIST, the attributes in ATTRIBUTE_BLACKLIST, and the
        module escapes.

        Args:
            code: Python source to check.

        Raises:
            PermissionError: If a blocked name or attribute is used.
            SyntaxError: If the code cannot be parsed.
        """

        tree = ast.parse(code)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                name = node.id

                is_dunder = name.startswith("__") and name.endswith("__")

                if is_dunder and name != "__name__":
                    raise PermissionError(f"access to '{name}' is not allowed")

            if isinstance(node, ast.Attribute):
                name = node.attr

                is_dunder = name.startswith("__") and name.endswith("__")

                if is_dunder and name not in DUNDERS_WHITELIST:
                    raise PermissionError(f"access to '{name}' is not allowed")

                if name in ATTRIBUTE_BLACKLIST or name in self.module_escapes:
                    raise PermissionError(f"access to '{name}' is not allowed")

    def _lockdown_module_escapes(self) -> set[str]:
        """Find attributes of allowed modules that lead to other modules.

        Imports the allowed modules, then scans every loaded allowed module for
        attributes whose value is a module that is not on the allowlist (e.g.
        random._os is the os module).

        Returns:
            The names of those attributes.
        """

        for permitted in self.allow_imports:
            if permitted.endswith(".*"):
                continue

            try:
                importlib.import_module(permitted)
            except ImportError:
                continue

        blocked: set[str] = set()

        for module_name, module in list(sys.modules.items()):
            if not self.is_allowed(module_name):
                continue

            for attr_name in dir(module):
                val = getattr(module, attr_name, None)

                if (isinstance(val, ModuleType)
                        and not self.is_allowed(val.__name__)):
                    blocked.add(attr_name)

        return blocked
