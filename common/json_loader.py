"""Load JSON files and validate them against Pydantic models."""

from json import JSONDecodeError, load
from pydantic import ValidationError, BaseModel
from typing import TypeVar
from sys import stderr


# Generic type for any Pydantic model,
# so json_loader returns the model it was given.
T = TypeVar("T", bound=BaseModel)


def json_loader(path: str, model: type[T]) -> T | None:
    """Load a JSON file and validate it against a Pydantic model.

    Errors are printed to stderr instead of raised.

    Args:
        path: Path to the JSON file.
        model: Pydantic model class to validate against.

    Returns:
        The validated model instance, or None on any read or validation error.
    """

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = load(f)

            return model.model_validate(content)

    except IOError as e:
        print(f"OSError: {e}", file=stderr)

    except JSONDecodeError as e:
        print(f"JSON error: {e}", file=stderr)

    except UnicodeDecodeError as e:
        print(f"Invalid encoding: {e}", file=stderr)

    except ValidationError as e:
        print("Validation error: ", end="", file=stderr)

        for err in e.errors():
            location = _format_err_location(err["loc"])
            print(f"{location}: {err['msg']}", file=stderr)

    return None


def _format_err_location(location: tuple) -> str:
    """Format a Pydantic error location as a readable field path.

    Args:
        location: The `loc` tuple from a Pydantic validation error.

    Returns:
        The path parts joined with ".", or "(whole file)" if empty.
    """

    parts: list[str] = []

    for part in location:
        parts.append(str(part))

    if not len(parts):
        return "(whole file)"

    return ".".join(parts)
