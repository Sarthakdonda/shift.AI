from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from app.core.errors import AppError
from app.models.schemas import Discovery, Scores, Necessity
from app.services.gemini_service import GeminiService


@pytest.mark.parametrize('classification', ['AI_REQUIRED','AI_OPTIONAL','AUTOMATION_SUFFICIENT','PROCESS_IMPROVEMENT','EXISTING_SOFTWARE_SUFFICIENT','HYBRID_SOLUTION'])
def test_all_decision_classes(classification):
    n = Necessity(classification=classification, score=50, reasoning=['Evidence'], non_ai_alternative='Rules', recommended_approach='Pilot', confidence=0.8)
    assert n.classification == classification


def test_invalid_decision_and_score_rejected():
    with pytest.raises(ValidationError):
        Necessity(classification='ALWAYS_USE_AI', score=101, reasoning=[], non_ai_alternative='', recommended_approach='', confidence=2)


def test_critical_missing_blocks_even_high_score():
    d = Discovery(collected_information=[], missing_information=['Outcome'], critical_missing=['Outcome'], scores=Scores(**{k: 99 for k in Scores.model_fields}), enough_information=True, next_question='What outcome matters most?')
    assert d.enough_information is False


def test_unknown_workflow_blocks_even_without_model_flag():
    d = Discovery(collected_information=[], missing_information=[], critical_missing=[], scores=Scores(business=100, problem=100, workflow=0, outcome=100), enough_information=True, next_question='Walk me through the current process?')
    assert d.enough_information is False and d.scores.overall == 30


def test_malformed_provider_output_retries_once(setup):
    ai = GeminiService()
    valid = setup[2].generate_structured('', {}, Necessity).model_dump_json()
    generate = Mock(side_effect=[SimpleNamespace(text='not json'), SimpleNamespace(text=valid)])
    ai.require = lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    result = ai.generate_structured('Decide', {}, Necessity)
    assert result.classification == 'AUTOMATION_SUFFICIENT'
    assert generate.call_count == 2
    generate.side_effect = [SimpleNamespace(text='{}'), SimpleNamespace(text='{}')]
    with pytest.raises(AppError) as e:
        ai.generate_structured('Decide', {}, Necessity)
    assert e.value.code == 'invalid_ai_output'
