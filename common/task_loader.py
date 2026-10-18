from json import JSONDecodeError, load
from pydantic import ValidationError, BaseModel
from argparse import ArgumentParser
from typing import TypeVar
from sys import stderr

T = TypeVar("T", bound=BaseModel)


def format_err_location(location: tuple) -> str:
    parts: list[str] = []

    for part in location:
        parts.append(str(part))

    if not len(parts):
        return "(whole file)"

    return ".".join(parts)


def loader(path: str, model: type[T]) -> T | None:
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
            location = format_err_location(err["loc"])
            print(f"{location}: {err['msg']}", file=stderr)

    return None


def setup_parser() -> ArgumentParser:
    parser = ArgumentParser(description="argument parser")
    parser.add_argument(
        "--task-file",
        type=str,
        required=True,
        help="path to the task JSON",
        )

    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="path where solution.json gets written"
        )

    parser.add_argument(
        "--model-name",
        type=str,
        required=False,
        help="model/name"
        )

    parser.add_argument(
        "--provider-url",
        type=str,
        required=False,
        help="URL for the api"
        )

    return parser
