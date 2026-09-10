"""Evidence-backed state merging and bounded question validation, independent of routes."""
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from pydantic import ValidationError
from app.agents import prompts
from app.core.errors import AppError
from app.models.schemas import Discovery
from app.models.project_context import ContextFact, ProjectContext, Question

logger = logging.getLogger(__name__)


def normalized(value: str) -> str:
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', value).casefold()))


def same_question(left: str, right: str) -> bool:
    a, b = normalized(left), normalized(right)
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.86


def load_memory(project, messages, documents) -> ProjectContext:
    memory = ProjectContext.model_validate(project.get('project_context') or {
        'stated_request': project['initial_problem'],
    })
    user_ids = {m['id'] for m in messages if m['role'] == 'user'}
    doc_ids = {d['id'] for d in documents if d['status'] == 'processed'}
    # Drop derived evidence if ANY supporting document was removed.
    active_ids = user_ids | doc_ids
    memory.known_facts = [f for f in memory.known_facts if set(f.source_ids) <= active_ids]
    memory.document_findings = []
    for document in documents:
        if document['id'] not in doc_ids:
            continue
        for fact in document.get('facts', []):
            memory.document_findings.append(ContextFact(
                category=fact['category'], topic=fact.get('topic') or normalized(fact['category'] + ' ' + fact['fact']),
                fact=fact['fact'], source=fact['source'], source_ids=[document['id']],
            ))
    # Legacy projects retain all historical questions; raw messages are migrated by the next call.
    existing = {normalized(q.question) for q in memory.questions_asked}
    for message in messages:
        if message['role'] == 'assistant' and message.get('message_type') == 'question' and normalized(message['content']) not in existing:
            memory.questions_asked.append(Question(question=message['content'][:1200], topic='legacy.' + message['id'],
                                                   reason='Previously asked question', priority='medium'))
    return memory


class DiscoveryService:
    def __init__(self, ai):
        self.ai = ai

    def run(self, context, all_messages):
        project = context['project']
        memory = load_memory(project, all_messages, context['documents'])
        user_ids = {m['id'] for m in all_messages if m['role'] == 'user'}
        doc_ids = {d['id'] for d in context['documents'] if d['status'] == 'processed'}
        pending = [m for m in all_messages if m['role'] == 'user' and m['id'] not in memory.processed_message_ids]
        payload = {
            'project': {k: project.get(k) for k in ('id', 'name', 'industry', 'initial_problem')},
            'project_context': memory.model_dump(),
            'unprocessed_user_messages': pending,
            'latest_user_message': next((m for m in reversed(all_messages) if m['role'] == 'user'), None),
            'messages': all_messages[-8:],
            **{k: context[k] for k in ('documents', 'evidence', 'output_language', 'workspace_policy', 'evidence_policy')},
        }
        # Normal path: one combined extraction/reasoning call. One repair only if invalid.
        for attempt in range(2):
            try:
                result = self.ai.generate_structured(prompts.DISCOVERY, payload, Discovery)
            except ValidationError:
                payload['validation_feedback'] = ['Return valid structured facts, questions and readiness matching the schema.']
                continue
            except AppError as exc:
                logger.warning('Discovery provider failure project=%s code=%s', project['id'], exc.code)
                raise
            issues = []
            active_ids = user_ids | doc_ids
            for fact in result.collected_information:
                if not set(fact.source_ids) <= active_ids:
                    issues.append(f'Fact topic {fact.topic} must cite only actual user-message or current-document IDs.')
            known = {normalized(f.topic) for f in memory.known_facts + memory.document_findings + result.collected_information}
            previous = list(memory.questions_asked)
            asked = {normalized(q.topic) for q in previous} | {normalized(t) for t in memory.answered_topics}
            for question in result.next_questions:
                key = normalized(question.topic)
                if key in known:
                    issues.append(f'Topic {question.topic} is already known. Ask about a different unresolved detail.')
                if key in asked or any(same_question(question.question, q.question) for q in previous):
                    issues.append(f'Topic {question.topic} repeats a prior question. Select a different unknown.')
                previous.append(question)
                asked.add(key)
            if result.enough_information and not (memory.known_facts or result.collected_information or memory.document_findings):
                issues.append('Analysis readiness requires sourced facts, not only completeness scores.')
            if issues:
                logger.info('Discovery validation project=%s attempt=%s rejected=%s', project['id'], attempt + 1, len(issues))
                payload['validation_feedback'] = issues
                # Include the candidate extraction so repair does not lose valid newly extracted facts.
                payload['rejected_response'] = result.model_dump()
                continue
            merged = {(normalized(f.topic), normalized(f.fact)): f for f in memory.known_facts}
            for fact in result.collected_information:
                key = normalized(fact.topic)
                old = [f for (topic, _), f in merged.items() if topic == key]
                # Document-only evidence cannot overwrite a user-confirmed statement.
                if any(set(f.source_ids) & user_ids for f in old) and not set(fact.source_ids) & user_ids:
                    continue
                if fact.replaces_existing and set(fact.source_ids) & user_ids:
                    merged = {k: v for k, v in merged.items() if k[0] != key}
                merged[(key, normalized(fact.fact))] = fact
            memory.known_facts = list(merged.values())
            memory.assumptions = list(dict.fromkeys(result.assumptions))
            confirmed = {normalized(f.topic) for f in memory.known_facts}
            memory.unknowns = [u for u in result.unknowns if normalized(u.topic) not in confirmed]
            historical = {normalized(q.topic) for q in memory.questions_asked}
            memory.answered_topics = list(dict.fromkeys(memory.answered_topics + [
                t for t in result.answered_topics if normalized(t) in historical
            ]))
            memory.questions_asked.extend(result.next_questions)
            memory.processed_message_ids = list(dict.fromkeys(memory.processed_message_ids + [m['id'] for m in pending]))
            memory.information_sufficiency = result.information_sufficiency
            memory.ready_for_analysis = result.enough_information
            memory.readiness_reason = result.readiness_reason
            # Keep the existing downstream evidence interface backed by the full durable memory.
            result.collected_information = memory.known_facts
            logger.info('Discovery project=%s stage=%s facts=%s unknowns=%s sufficiency=%s ready=%s',
                        project['id'], 'SYSTEM_ANALYSIS' if result.enough_information else 'DISCOVERY',
                        len(memory.known_facts), len(memory.unknowns), result.information_sufficiency, result.enough_information)
            return result, memory
        raise AppError('We could not prepare a useful new question. Your answer is saved; please retry.', 502, 'discovery_validation')
