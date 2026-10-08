"""Staged app building with Groq first and Gemini as a separate provider fallback."""
import copy
import logging

from app.core.errors import AppError
from app.services.gemini_service import get_gemini
from app.services.groq_service import GroqService, POLICY

logger = logging.getLogger(__name__)
FALLBACK_ERRORS = {
    'rate_limited', 'groq_quota_exhausted', 'provider_unavailable',
    'groq_configuration', 'provider_error', 'groq_request_budget',
    'groq_context_length', 'groq_output_limit', 'invalid_ai_output',
}


class BuilderAI(GroqService):
    provider = 'builder'

    def __init__(self):
        super().__init__()
        # Share key cooldowns with discovery, but isolate the builder prompt and
        # request-specific cancellation callback from the cached Gemini service.
        self.gemini = copy.copy(get_gemini()) if self.settings.builder_gemini_fallback else None
        if self.gemini is not None:
            self.gemini.system_instruction = POLICY
        if self.has_gemini:
            # Try eligible Groq credentials, then use Gemini without a long sleep.
            self.cooldown_wait_seconds = 0

    @property
    def has_gemini(self):
        return self.gemini is not None and bool(self.gemini._keys)

    @property
    def model_identity(self):
        if self.has_gemini:
            return f'groq:{self.settings.groq_model}|gemini:{self.gemini.settings.gemini_model}'
        return self.settings.groq_model

    def require(self):
        if self._keys:
            return self
        if self.has_gemini:
            self.gemini.require()
            return self
        raise AppError('Configure GROQ_API_KEY(S), or enable BUILDER_GEMINI_FALLBACK '
                       'with GEMINI_API_KEY(S), then restart the backend and builder workers.',
                       503, 'builder_configuration')

    def generate_structured(self, instruction, context, schema, *, output_tokens=None):
        self.require()
        if hasattr(self, 'check_cancelled'):
            self.check_cancelled()
        if self._keys:
            try:
                return super().generate_structured(instruction, context, schema, output_tokens=output_tokens)
            except AppError as exc:
                if not self.has_gemini or exc.code not in FALLBACK_ERRORS:
                    raise
                logger.info('Builder using Gemini after Groq failure (%s).', exc.code)
        fallback = copy.copy(self.gemini)
        if hasattr(self, 'check_cancelled'):
            fallback.check_cancelled = self.check_cancelled
            self.check_cancelled()
        return fallback.generate_structured(instruction, context, schema)
