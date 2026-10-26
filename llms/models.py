"""Pydantic models for the LLM provider configuration."""

from pydantic import BaseModel, Field, model_validator, field_validator


class LLMProvider(BaseModel):
    """One provider entry from the models config file.

    Attributes:
        name: Provider name, e.g. "groq".
        base_url: Base URL of the provider's OpenAI-compatible API, starting
            with http:// or https://.
        key_prefix: Prefix of the environment variables that hold the
            provider's API keys, e.g. GROQ_API_KEY.
    """

    name: str = Field(min_length=1)
    base_url: str = Field(min_length=5)
    key_prefix: str = Field(min_length=1)

    @model_validator(mode='after')
    def validate_url(self) -> "LLMProvider":
        """Check that base_url starts with http:// or https://.

        Returns:
            The validated provider.

        Raises:
            ValueError: If base_url starts with neither.
        """

        if (not self.base_url.startswith("http://")
                and not self.base_url.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")

        return self


class LLMProviderList(BaseModel):
    providers: list[LLMProvider] = Field(min_length=1)


class LLMModelData(BaseModel):
    base_url: str = Field(min_length=5)
    model_name: str = Field(min_length=1)
    api_keys: list[str] = Field(min_length=1)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if (not value.startswith("http://")
                and not value.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")

        return value


class RequestData(BaseModel):
    text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    response_time_in_ms: float = Field(ge=0.0)
    reply_code: int = Field(ge=0)
