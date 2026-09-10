import logging
import copy
from uuid import uuid4
from datetime import timedelta
from app.agents import prompts
from app.core.errors import AppError
from app.models.schemas import DocumentSummary
from app.models.deliverables import LANGUAGES
from app.repositories.store import now, serialize
from app.services.document_service import extract
from app.services.retrieval_service import retrieve
from app.services.discovery_service import DiscoveryService, load_memory
from app.services.generation_service import Generation, CancellableAI
from app.workflows.shift_graph import build_graph

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, store, ai):
        self.store, self.ai = store, ai
        self.generation = None

    def context(self, pid, owner):
        p = self.store.project(pid, owner)
        policy = {}
        overrides = {}
        if p.get('workspace_id'):
            w = self.store.workspace(p['workspace_id'], owner)
            policy = {k: w.get(k) for k in ['ai_policy', 'retention_days', 'model']}
            if w.get('model'):
                overrides['gemini_model'] = w['model']
        # The project choice made in the composer wins over the workspace default.
        if p.get('model'):
            overrides['gemini_model'] = p['model']
        if p.get('effort'):
            overrides['gemini_effort'] = p['effort']
            # A stored effort replaces any fixed thinking level from the environment.
            overrides['gemini_thinking_level'] = None
        if overrides and hasattr(self.ai.settings, 'model_copy'):
            self.ai = copy.copy(self.ai)
            self.ai.settings = self.ai.settings.model_copy(update=overrides)
        messages = self.store.related('messages', pid)
        query = p['initial_problem'] + ' ' + ' '.join(m['content'] for m in messages[-4:])
        chunks, warnings = retrieve(self.store, self.ai, pid, query)
        documents = serialize(self.store.related('documents', pid))
        memory = load_memory(serialize(p), serialize(messages), documents)
        return {'project': serialize(p), 'project_context': memory.model_dump(), 'outcomes': serialize(list(self.store.db.outcomes.find({'project_id':pid}).sort('created_at',-1).limit(20))), 'output_language': LANGUAGES.get(p.get('language', 'en'), p.get('language', 'en')), 'workspace_policy': policy, 'messages': serialize(messages[-8:]), 'previous_discovery': p.get('discovery'), 'documents': documents, 'evidence': chunks, 'retrieval_warnings': warnings,
                'evidence_policy': 'Current documents and user messages are authoritative. Earlier assistant messages are conversational questions, not independent factual evidence. Do not reuse facts from removed documents.'}

    def discover(self, pid, owner):
        context = self.context(pid, owner)
        result, memory = DiscoveryService(self.ai).run(context, serialize(self.store.related('messages', pid)))
        if self.generation:
            self.generation.check()
        self.store.update(pid, project_context=memory.model_dump(), discovery=result.model_dump(), discovery_scores=result.scores.model_dump(), analysis_ready=result.enough_information, status='DISCOVERY', error=None, retrieval_warnings=context['retrieval_warnings'])
        message = result.next_question or 'We have enough context. I’m starting the analysis of your workflow and the underlying problem.'
        self.store.message(pid, 'assistant', message, message_type='status' if result.enough_information else 'question')
        return {'message': message, 'stage': 'DISCOVERY', 'discovery_scores': result.scores.model_dump(), 'needs_user_input': not result.enough_information, 'analysis_ready': result.enough_information, 'project_id': pid}

    def chat(self, pid, owner, content=None, tasks=None, request_id=None):
        self.store.project(pid, owner, 'write')
        generation_id = request_id or str(uuid4())
        self.generation = Generation(self.store, pid, generation_id)
        self.generation.check()
        self.store.acquire(pid, owner)
        handed_off = False
        try:
            self.store.update(pid, active_generation_id=generation_id)
            self.ai = CancellableAI(self.ai, self.generation)
            project = self.store.project(pid, owner)
            messages = self.store.related('messages', pid)
            last_user = next((m for m in reversed(messages) if m['role'] == 'user'), None)
            previous_request = next((m for m in messages if request_id and m.get('request_id') == request_id), None)
            if previous_request and previous_request['content'].strip() != content.strip():
                raise AppError('This request was already used for a different answer. Please send again.', 409)
            duplicate = previous_request or (content is not None and last_user and messages[-1]['role'] == 'user'
                                              and last_user['content'].strip() == content.strip())
            # A retried HTTP request must neither duplicate an answer nor start another analysis.
            if (not content or duplicate) and project.get('discovery') and messages[-1]['role'] == 'assistant':
                return {'message': messages[-1]['content'], 'stage': project['status'], 'project_id': pid,
                        'analysis_ready': project['analysis_ready'], 'needs_user_input': not project['analysis_ready'],
                        'discovery_scores': project['discovery_scores']}
            if content and not duplicate:
                self.store.message(pid, 'user', content, request_id=request_id)
                self.store.invalidate(pid)
            result = self.discover(pid, owner)
            self.generation.check()
            if result['analysis_ready'] and tasks is not None:
                self.store.update(pid, status='SYSTEM_ANALYSIS')
                tasks.add_task(self.analyze, pid, owner)
                handed_off = True
                result['stage'] = 'SYSTEM_ANALYSIS'
            return result
        finally:
            if not handed_off:
                self.store.update(pid, busy=False, active_generation_id=None)

    def analyze(self, pid, owner):
        try:
            context = self.context(pid, owner)

            def progress(stage, state):
                if self.generation:
                    self.generation.check()
                self.store.update(pid, status=stage, lease_until=now() + timedelta(minutes=30))
                self.store.save_analysis(pid, {k: v for k, v in state.items() if k != 'context'})

            result = build_graph(self.ai, progress).invoke({'context': context, 'red_team_cycle': 0, 'red_team_history': []}, {'recursion_limit': 30})
            if self.generation:
                self.generation.check()
            content = {k: v for k, v in result.items() if k != 'context'}
            content['problem_statement'] = context['project']['initial_problem']
            content['evidence'] = context['previous_discovery']['collected_information'] if context['previous_discovery'] else []
            content['retrieval_warnings'] = context['retrieval_warnings']
            self.store.save_analysis(pid, content)
            self.store.save_blueprint(pid, content)
            self.store.update(pid, status='BLUEPRINT_READY', ai_necessity=content['ai_necessity'], error=None)
            self.store.message(pid, 'assistant', 'Your blueprint is ready. Review the diagnosis, recommended solution, Red Team findings, and implementation roadmap.', message_type='status')
        except Exception as exc:
            if isinstance(exc, AppError) and exc.code == 'generation_cancelled':
                self.store.update(pid, status='DISCOVERY', error=None)
                return
            message = exc.message if isinstance(exc, AppError) else 'Analysis was interrupted. Your discovery is saved; please run analysis again.'
            logger.warning('Analysis failed (%s)', type(exc).__name__)
            self.store.update(pid, status='ERROR', error=message)
        finally:
            self.store.update(pid, busy=False, active_generation_id=None)

    def process_document(self, pid, owner, did, data, ext, filename):
        try:
            self.store.update(pid, status='DOCUMENT_ANALYSIS')
            chunks = extract(data, ext)
            for c in chunks:
                c.update(project_id=pid, document_id=str(did))
                c['metadata']['filename'] = filename
            self.store.db.document_chunks.insert_many(chunks)
            # Summarize all content in bounded batches, then consolidate facts.
            summaries = []
            for start in range(0, len(chunks), 35):
                summaries.append(self.ai.generate_structured(prompts.DOCUMENT, chunks[start:start + 35], DocumentSummary).model_dump())
            summary = summaries[0] if len(summaries) == 1 else self.ai.generate_structured(prompts.DOCUMENT, summaries, DocumentSummary).model_dump()
            warnings = []
            if self.ai.settings.vector_search_enabled:
                try:
                    for c in chunks:
                        vector = self.ai.embed(c['text'])
                        self.store.db.document_chunks.update_one({'_id': c['_id']}, {'$set': {'embedding': vector}})
                except AppError:
                    warnings.append('Embedding unavailable; this file uses keyword retrieval.')
            self.store.db.documents.update_one({'_id': did, 'project_id': pid}, {'$set': {**summary, 'status': 'processed', 'chunk_count': len(chunks), 'warnings': warnings}})
            self.store.invalidate(pid)
            result = self.discover(pid, owner)
            if result['analysis_ready']:
                self.analyze(pid, owner)
        except Exception as exc:
            message = exc.message if isinstance(exc, AppError) else 'Document processing failed. Please try again.'
            # A discovery failure does not discard an already processed document.
            doc = self.store.db.documents.find_one({'_id': did})
            if doc and doc['status'] != 'processed':
                self.store.db.documents.update_one({'_id': did}, {'$set': {'status': 'failed', 'error': message}})
                self.store.db.document_chunks.delete_many({'project_id': pid, 'document_id': str(did)})
            self.store.update(pid, status='DISCOVERY', error=message)
        finally:
            self.store.update(pid, busy=False)
