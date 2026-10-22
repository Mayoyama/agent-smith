"""Restrictions applied to code running in the sandbox worker."""
from common import SandboxConfig
from typing import Any, Mapping, Sequence
from types import ModuleType
import builtins
import os


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

    def open_file(self, path: str, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(path, str):
            raise PermissionError("only file paths are allowed")

        real_path = os.path.realpath(path)

        for allowed_dir in self.resolved_dirs:
            if (allowed_dir == real_path
                    or real_path.startswith(allowed_dir + os.sep)):
                return builtins.open(real_path, *args, **kwargs)

        raise PermissionError(f"access to {path} is not allowed")
