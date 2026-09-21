"""Keep provider schemas small without weakening saved-document validation."""
from pydantic import BaseModel


class ProviderModel(BaseModel):
    @classmethod
    def provider_json_schema(cls):
        """Send shape/enums; enforce bounds and relationships with Pydantic.

        Nested collection bounds can exhaust Gemini's schema compilation budget.
        Property names such as ``title`` must remain intact when removing metadata.
        """
        def compact(value):
            if isinstance(value, dict):
                return {k: ({name: compact(child) for name, child in v.items()} if k in {'properties', '$defs'} else compact(v)) for k, v in value.items() if k not in {
                    'title', 'minItems', 'maxItems', 'minLength', 'maxLength', 'minimum', 'maximum', 'pattern'}}
            if isinstance(value, list):
                return [compact(v) for v in value]
            return value
        return compact(cls.model_json_schema())
