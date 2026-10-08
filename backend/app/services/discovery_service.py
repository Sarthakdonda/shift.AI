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


def is_non_answer(value: str) -> bool:
    """Recognize only empty/punctuation and standalone social turns.

    Short answers (yes/no, names, numbers) still go to contextual interpretation.
    A greeting followed by business details is also a real answer.
    """
    text = normalized(value)
    if not any(c.isalnum() for c in text):
        return True
    if text in {normalized(word) for word in ('नमस्ते', 'नमस्कार', '你好', 'مرحبا', 'سلام')}:
        return True
    return bool(re.fullmatch(r'(?:h+i+|h+e+y+|h+e+l+o+|hello|hi there|hey there|hello there|good morning|good evening|good afternoon|thanks|thank you|ok|okay|hmm+|namaste|नमस्ते|नमस्कार|hola|bonjour|你好|مرحبا|سلام)(?:\s+(?:shift\s*ai|there|again))?', text))


def readiness_issues(evidence, messages, documents):
    """Validate the quoted support independently of model scores and prose."""
    sources = {m['id']: normalized(m['content']) for m in messages
               if m['role'] == 'user' and not is_non_answer(m['content'])}
    for document in documents:
        if document['status'] == 'processed':
            sources[document['id']] = normalized(document.get('summary', '') + ' ' + ' '.join(f['fact'] for f in document.get('facts', [])))
    supported = set()
    for item in evidence:
        quote = normalized(item.quote)
        if quote and not is_non_answer(quote) and quote in sources.get(item.source_id, ''):
            supported.add(item.criterion)
    return [f'Readiness needs an exact supporting user/document quote for {criterion}; scores and assumptions are not evidence.'
            for criterion in ('problem', 'workflow', 'outcome') if criterion not in supported]


def same_question(left: str, right: str) -> bool:
    a, b = normalized(left), normalized(right)
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.86


def load_memory(project, messages, documents) -> ProjectContext:
    memory = ProjectContext.model_validate(project.get('project_context') or {
        'stated_request': project['initial_problem'],
    })
    user_ids = {m['id'] for m in messages if m['role'] == 'user' and not is_non_answer(m['content'])}
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
        if message['role'] == 'assistant' and message.get('message_type') == 'question':
            questions = [Question.model_validate(q) for q in message.get('questions', [])] or [
                Question(question=message['content'][:1200], topic='legacy.' + message['id'], reason='Previously asked question', priority='medium')]
            for question in questions:
                if normalized(question.question) not in existing:
                    memory.questions_asked.append(question)
                    existing.add(normalized(question.question))
    return memory


class DiscoveryService:
    def __init__(self, ai):
        self.ai = ai
        # Set when a question has to be repeated, so the card can explain why.
        self.notice = ''

    def run(self, context, all_messages):
        project = context['project']
        memory = load_memory(project, all_messages, context['documents'])
        user_ids = {m['id'] for m in all_messages if m['role'] == 'user' and not is_non_answer(m['content'])}
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
        candidate = None
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
            issues = self.issues(result, memory, user_ids, doc_ids, all_messages, context['documents'])
            if not issues:
                return self.commit(result, memory, user_ids, pending, project)
            logger.info('Discovery validation project=%s attempt=%s rejected=%s', project['id'], attempt + 1, len(issues))
            candidate = result
            payload['validation_feedback'] = issues
            # Include the candidate extraction so repair does not lose valid newly extracted facts.
            payload['rejected_response'] = result.model_dump()
        if candidate is None:
            raise AppError('The AI response could not be validated. Your answer is saved; please retry.', 502, 'invalid_ai_output')
        # Bounded provider repair did not converge. Repair the candidate locally instead of
        # ending a saved answer in an error: nothing is invented, unsourced facts and
        # duplicate questions are dropped, and unverified readiness stays unverified.
        try:
            repaired = self.repair(candidate, memory, user_ids, doc_ids, all_messages, context['documents'])
        except ValidationError:
            raise AppError('We could not prepare the next question from the AI response. Your answer is saved; please retry.', 502, 'invalid_ai_output') from None
        logger.info('Discovery repaired locally project=%s facts=%s ready=%s',
                    project['id'], len(repaired.collected_information), repaired.enough_information)
        return self.commit(repaired, memory, user_ids, pending, project)

    @staticmethod
    def issues(result, memory, user_ids, doc_ids, messages, documents):
        """Reject unsourced facts, redundant questions and unverified readiness."""
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
        if result.enough_information:
            issues.extend(readiness_issues(result.readiness_evidence, messages, documents))
            if not (memory.known_facts or result.collected_information or memory.document_findings):
                issues.append('Analysis readiness requires sourced facts, not only completeness scores.')
        return issues

    def repair(self, candidate, memory, user_ids, doc_ids, messages, documents):
        """Turn a rejected candidate into a usable turn without inventing anything."""
        active_ids = user_ids | doc_ids
        facts = [f for f in candidate.collected_information if set(f.source_ids) <= active_ids]
        known = {normalized(f.topic) for f in memory.known_facts + memory.document_findings + facts}
        asked = {normalized(q.topic) for q in memory.questions_asked} | {normalized(t) for t in memory.answered_topics}
        questions = []
        for question in candidate.next_questions:
            key = normalized(question.topic)
            if key in known or key in asked or any(same_question(question.question, q.question)
                                                   for q in memory.questions_asked + questions):
                continue
            questions.append(question)
            asked.add(key)
        ready = bool(candidate.enough_information
                     and not readiness_issues(candidate.readiness_evidence, messages, documents)
                     and (facts or memory.known_facts or memory.document_findings))
        if not questions:
            questions = [self.open_question(candidate, memory, known)]
        data = candidate.model_dump()
        data.update(collected_information=[f.model_dump() for f in facts],
                    next_questions=[q.model_dump() for q in questions],
                    enough_information=ready,
                    readiness_evidence=data['readiness_evidence'] if ready else [])
        if candidate.enough_information and not ready:
            data['readiness_reason'] = 'Readiness needs an exact supporting quote from your messages or documents, so discovery continues.'
        return Discovery.model_validate(data)

    def open_question(self, candidate, memory, known):
        """Re-ask the still-open question, or ask for the highest-priority unknown."""
        answered = {normalized(t) for t in memory.answered_topics} | known
        for question in reversed(memory.questions_asked):
            if normalized(question.topic) not in answered:
                self.notice = 'I still need this detail before we can go further.'
                return question.model_copy(update={'priority': 'high'})
        self.notice = 'Let’s pin down one more detail.'
        unresolved = [u for u in list(candidate.unknowns) + list(memory.unknowns) if normalized(u.topic) not in answered]
        if unresolved:
            top = min(unresolved, key=lambda u: {'high': 0, 'medium': 1, 'low': 2}.get(u.priority, 1))
            subject = top.topic.replace('.', ' ').replace('_', ' ').strip() or 'how this works today'
            return Question(question=f'Could you describe {subject} in your own words?'[:1200], topic=top.topic,
                            reason=top.reason, priority='high', label='Your project',
                            hint='A short, factual answer is enough.')
        gap = next((g.strip() for g in list(candidate.critical_missing) + list(candidate.missing_information) if g.strip()), '')
        return Question(question=(f'Could you tell us more about this? {gap}'[:1200] if gap
                                  else 'What else matters about how this works today?'),
                        topic='problem.additional_detail', reason=gap or 'More project context is needed before analysis.',
                        priority='high', label='Your project', hint='A short, factual answer is enough.')

    def commit(self, result, memory, user_ids, pending, project):
        """Merge an accepted result into durable memory."""
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
        # A repeated question must not be stored twice.
        recorded = {normalized(q.question) for q in memory.questions_asked}
        for question in result.next_questions:
            if normalized(question.question) not in recorded:
                memory.questions_asked.append(question)
                recorded.add(normalized(question.question))
        memory.processed_message_ids = list(dict.fromkeys(memory.processed_message_ids + [m['id'] for m in pending]))
        memory.information_sufficiency = result.information_sufficiency
        memory.ready_for_analysis = result.enough_information
        memory.readiness_reason = result.readiness_reason
        memory.readiness_evidence = result.readiness_evidence if result.enough_information else []
        # Keep the existing downstream evidence interface backed by the full durable memory.
        result.collected_information = memory.known_facts
        logger.info('Discovery project=%s stage=%s facts=%s unknowns=%s sufficiency=%s ready=%s',
                    project['id'], 'SYSTEM_ANALYSIS' if result.enough_information else 'DISCOVERY',
                    len(memory.known_facts), len(memory.unknowns), result.information_sufficiency, result.enough_information)
        return result, memory
