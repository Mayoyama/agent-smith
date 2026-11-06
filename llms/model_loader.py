"""Load the provider config and the API keys for the chosen provider."""

from .models import LLMProvider, LLMProviderList, LLMModelData
from common import json_loader
from sys import stderr
import dotenv
import os
from urllib.parse import urlparse


def guess_provider(provider_url: str) -> LLMProvider:
    """Build a provider entry for a URL missing from the config file.

    The key prefix comes from the host name without a leading api. or www.
    and without its last label: https://api.together.xyz/v1 gives
    TOGETHER_API_KEY.

    Args:
        provider_url: Base URL of the provider's API, from --provider-url.

    Returns:
        A provider with that URL and the guessed key prefix.

    Raises:
        ValueError: If the URL is not a valid http(s) URL.
    """

    host: str = urlparse(provider_url).hostname or ""
    labels: list[str] = host.split(".")

    if len(labels) > 2 and labels[0] in ("api", "www"):
        labels = labels[1:]

    name: str = labels[-2] if len(labels) >= 2 else labels[0]
    name = name.replace("-", "_")

    return LLMProvider(
        name=name,
        base_url=provider_url,
        key_prefix=f"{name.upper()}_API_KEY",
    )


def validate_llm_providers(
    config_path: str, model_name: str, provider_url: str,
) -> LLMModelData:
    """Find the provider for a URL and collect its API keys.

    Loads .env into the environment (a missing file only prints a warning),
    loads the provider config and picks the provider whose base_url matches
    provider_url, ignoring trailing slashes (an unknown URL gets a provider
    guessed by guess_provider). Its keys are read from the plain
    variable <key_prefix>, then from the numbered variables <key_prefix>_1,
    <key_prefix>_2 and so on until one is missing or empty; empty values are
    skipped.

    Args:
        config_path: Path to the provider config JSON file.
        model_name: Model to request, e.g. "openai/gpt-oss-20b".
        provider_url: Base URL of the provider's API, from --provider-url.

    Returns:
        The provider's base URL, the model name and the API keys.

    Raises:
        RuntimeError: If the config file can't be loaded.
        ValueError: If the URL is not a valid http(s) URL, or no API key is
            set for the provider (configured, or guessed from the host when
            the URL is not in the config).
    """

    loaded = dotenv.load_dotenv()
    llm_provider: LLMProvider | None = None

    if not loaded:
        print("no .env detected", file=stderr)

    provider_list = json_loader(config_path, LLMProviderList)

    if provider_list is None:
        raise RuntimeError(f"unable to load config '{config_path}'")

    for provider in provider_list.providers:
        if provider.base_url.rstrip('/') == provider_url.rstrip('/'):
            llm_provider = provider

    if llm_provider is None:
        llm_provider = guess_provider(provider_url)

    api_keys: list[str] = []

    base_key = os.environ.get(llm_provider.key_prefix)

    if base_key:
        api_keys.append(base_key)

    index = 1

    while True:
        key_string = f"{llm_provider.key_prefix}_{index}"

        key = os.environ.get(key_string, None)

        if not key:
            break

        api_keys.append(key)
        index += 1

    if not api_keys:
        raise ValueError(f"missing api key: set {llm_provider.key_prefix} or"
                         f" {llm_provider.key_prefix}_1")

    model_data = LLMModelData(
        base_url=llm_provider.base_url,
        model_name=model_name,
        api_keys=api_keys,
    )

    return model_data
