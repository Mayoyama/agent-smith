from .models import LLMProvider, LLMProviderList, LLMModelData
from common import json_loader
from sys import stderr
import dotenv
import os


def validate_llm_providers(
    config_path: str,
    model_name: str,
    provider_url: str
) -> LLMModelData:
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
        raise ValueError(f"no provider config for '{provider_url}'")

    api_keys: list[str] = []

    index = 1

    while True:
        key_string = f"{llm_provider.key_prefix}_{index}"

        key = os.environ.get(key_string, None)

        if key is None:
            if index == 1:
                raise ValueError(f"missing api key {key_string}")

            break

        api_keys.append(key)
        index += 1

    model_data = LLMModelData(
        base_url=llm_provider.base_url,
        model_name=model_name,
        api_keys=api_keys,
    )

    return model_data
