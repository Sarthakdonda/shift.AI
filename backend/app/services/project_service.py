import logging
from app.agents import prompts
from app.core.errors import AppError
from app.models.schemas import Discovery, DocumentSummary
from app.repositories.store import now, serialize
from app.services.document_service import extract
from app.services.retrieval_service import retrieve
from app.workflows.shift_graph import build_graph

logger = logging.getLogger(__name__)


class ProjectService:
    def __init__(self, store, ai):
        self.store, self.ai = store, ai

    def context(self, pid, owner):
        p = self.store.project(pid, owner)
        messages = self.store.related('messages', pid)
        query = p['initial_problem'] + ' ' + ' '.join(m['content'] for m in messages[-4:])
        chunks, warnings = retrieve(self.store, self.ai, pid, query)
        return {'project': serialize(p), 'messages': serialize(messages[-60:]), 'previous_discovery': p.get('discovery'), 'documents': serialize(self.store.related('documents', pid)), 'evidence': chunks, 'retrieval_warnings': warnings,
                'evidence_policy': 'Current documents and user messages are authoritative. Earlier assistant messages are conversational questions, not independent factual evidence. Do not reuse facts from removed documents.'}

    def discover(self, pid, owner):
        context = self.context(pid, owner)
        result = self.ai.generate_structured(prompts.DISCOVERY, context, Discovery)
        self.store.update(pid, discovery=result.model_dump(), discovery_scores=result.scores.model_dump(), analysis_ready=result.enough_information, status='DISCOVERY', error=None, retrieval_warnings=context['retrieval_warnings'])
        message = result.next_question or 'We have enough context to analyze your business problem. Start analysis when you are ready.'
        self.store.message(pid, 'assistant', message, message_type='question')
        return {'message': message, 'stage': 'DISCOVERY', 'discovery_scores': result.scores.model_dump(), 'needs_user_input': not result.enough_information, 'analysis_ready': result.enough_information, 'project_id': pid}

    def chat(self, pid, owner, content=None):
        self.ai.require()
        self.store.acquire(pid, owner)
        try:
            if content:
                self.store.message(pid, 'user', content)
                self.store.invalidate(pid)
            return self.discover(pid, owner)
        finally:
            self.store.update(pid, busy=False)

    def analyze(self, pid, owner):
        try:
            context = self.context(pid, owner)

            def progress(stage, state):
                self.store.update(pid, status=stage)
                self.store.save_analysis(pid, {k: v for k, v in state.items() if k != 'context'})

            result = build_graph(self.ai, progress).invoke({'context': context, 'red_team_cycle': 0, 'red_team_history': []}, {'recursion_limit': 30})
            content = {k: v for k, v in result.items() if k != 'context'}
            content['problem_statement'] = context['project']['initial_problem']
            content['evidence'] = context['previous_discovery']['collected_information'] if context['previous_discovery'] else []
            content['retrieval_warnings'] = context['retrieval_warnings']
            self.store.save_analysis(pid, content)
            self.store.save_blueprint(pid, content)
            self.store.update(pid, status='BLUEPRINT_READY', ai_necessity=content['ai_necessity'], error=None)
            self.store.message(pid, 'assistant', 'Your blueprint is ready. Review the diagnosis, recommended solution, Red Team findings, and implementation roadmap.', message_type='status')
        except Exception as exc:
            message = exc.message if isinstance(exc, AppError) else 'Analysis was interrupted. Your discovery is saved; please run analysis again.'
            logger.warning('Analysis failed (%s)', type(exc).__name__)
            self.store.update(pid, status='ERROR', error=message)
        finally:
            self.store.update(pid, busy=False)

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
            self.discover(pid, owner)
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
