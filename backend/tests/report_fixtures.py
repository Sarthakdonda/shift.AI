"""Synthetic invoice design used for contract and PDF layout verification only."""
from app.models.final_report import PART_SCHEMAS


def estimate(label, unit, low=None, high=None):
    return dict(label=label, low=low, high=high, unit=unit,
                basis='Illustrative planning assumption; no vendor quote or measured baseline supplied.',
                assumptions=['Confirm scope, staff availability and rates with the operations owner.'],
                confidence='unknown' if low is None else 'low')


def decision_fixture():
    options = []
    scopes = ['Standardize spreadsheet entry and review.', 'Add a validated invoice import service with human review.', 'Introduce a multi-team integration platform and stronger governance.']
    approaches = ['Configure the existing spreadsheet and a review checklist.', 'Small deterministic importer with a relational audit store.', 'Central integration runtime with separate work queues and managed identity.']
    for i, tier in enumerate(['lean', 'balanced', 'advanced']):
        options.append(dict(tier=tier, title=['Lean process pilot','Balanced import workflow','Advanced integration platform'][i],
            scope=scopes[i], approach=approaches[i], included=[scopes[i]], excluded=['Automated payments', 'AI extraction'],
            ai_usage='none', ai_reason='Fixed fields and explicit validation rules do not need AI.',
            integrations_and_data=['Accounting import format and credentials require validation.'],
            security_and_governance='Role-limited access and audit records; jurisdiction and retention require validation.',
            effort=estimate('Implementation effort','person-days', [3,10,30][i], [5,20,60][i]),
            duration=estimate('Elapsed duration','weeks', [1,3,8][i], [2,6,14][i]), cost=estimate('Setup cost','Currency to confirm'),
            team_and_ownership=['Operations owner approves rules; delivery engineer implements the pilot.'],
            benefits=['Reduce duplicate entry and make exception handling visible.'],
            limitations=[['Manual retyping remains','Requires a maintained import service','Higher operational burden'][i]],
            risks_and_mitigations=['Unverified integration: validate CSV format and reconcile a sample before rollout.'],
            scalability=['One team','Several teams with bounded imports','Multi-team governance'][i],
            best_fit=['Very limited budget','Repeatable invoice workload','Many systems and large transaction volumes'][i],
            avoid_when=['Volume makes manual entry impractical','No engineering owner is available','Current scale cannot justify additional infrastructure'][i]))
    criteria = []
    for name, weight, scores in [('Business fit',40,[2,5,4]),('Cost fit',30,[5,4,1]),('Time to value',30,[5,4,2])]:
        criteria.append(dict(name=name, weight=weight, basis='Assumed priority: confirm with operations owner.',
            scores=[dict(tier=tier, score=score, reason='Advisory fit for a small operations team.') for tier, score in zip(['lean','balanced','advanced'], scores)]))
    return dict(options=options, criteria=criteria, selected='balanced', selection_reason='Balances removal of duplicate entry with manageable delivery effort.',
        rejection_reasons=[dict(tier='lean',score=3,reason='Retains manual retyping.'),dict(tier='advanced',score=2,reason='Scale and governance burden are not justified.')],
        decision_sensitivities=['Choose lean if no engineer can maintain the importer.'])


COPY = {
 'scope': ('Detailed scope and acceptance criteria','Import validated invoice rows, detect duplicates and require review before accounting export.', [['REQ-1','Reject duplicate supplier/reference pairs; preserve a reason for every rejected row.'],['Out of scope','Do not automate payments or infer invoice fields using AI.']]),
 'stack': ('Technology stack and rationale','Use deterministic validation and a small persistent audit trail; verify existing hosting before choosing a vendor.', [['Backend','Python service: simple CSV validation; alternative is existing accounting import configuration.'],['Data store','Relational audit store; use the current supported database if available.'],['Identity','Reuse the organization identity provider if accessible; do not assume it exists.']]),
 'hld': ('High-level architecture','Operations supplies structured invoices to the Invoice importer, reviews exceptions, then approves the accounting handoff.', []),
 'lld': ('Low-level component design','Invoice importer owns parsing, field checks, deduplication and export audit. Human approval precedes external changes.', [['Input / output','CSV invoice rows → accepted rows, exception report and approved export.'],['Business rule','Unique supplier/reference; required amount and date; reject malformed rows.'],['Failure / security','Reject malformed imports atomically, audit attempt, require reviewer permission.']]),
 'security': ('Security, privacy and governance','Restrict invoice access to operations reviewers; record approvals and support access. Confirm retention, jurisdiction and accounting permissions before pilot.', [['Boundary','No payment credentials or automatic payment authorization.'],['Control','Encrypted transport, least-privilege access and auditable export approval.']]),
 'infrastructure': ('Infrastructure and cloud architecture','Pilot in an isolated environment with bounded file storage, private database access and monitored job outcomes.', [['Backup / recovery','Agree recovery objectives, then test restoring the invoice audit trail.'],['Scale / secrets','Limit file size; keep credentials server-side in the approved secrets store.']]),
 'deployment': ('Deployment and release architecture','Validate in test, reconcile a representative sample, then promote an approved release. Operations owns go-live approval.', [['CI/CD','Run schema and duplicate-handling checks before promotion.'],['Rollback','Stop new imports, retain audit data and return to reviewed manual entry.']]),
 'operating_model': ('Human checkpoints and operating model','Operations reviews exceptions and approves each export. The delivery engineer investigates failed jobs; the operations owner owns reconciliation.', [['Checkpoint','Do not export until exceptions are resolved or explicitly excluded.']]),
 'stakeholders': ('Stakeholders and personas','Operations staff wants less duplicate entry; the reviewer needs a clear approval trail; the owner needs reconciled records.', [['Operations staff','Upload records, correct errors and view assigned imports.'],['Reviewer','Approve exports; cannot change payment permissions.']]),
 'future_process': ('Future-state workflow and approval flows','Upload records, validate fields and duplicates, resolve exceptions, review and approve export, then reconcile the result.', []),
 'journeys': ('User journeys and navigation','An operations user starts in the import queue, uploads a CSV, reviews exceptions and hands approved records to the reviewer. Failure returns the user to correction with row-specific guidance.', [['Goal / end state','Approved export is reconciled with the source invoice count.'],['Permissions / exceptions','Only reviewers approve; invalid files stay in correction and produce no export.']]),
 'wireframes': ('Key screen concepts','Use an import queue, exception review and audit history. All views need empty, loading, success and error states with accessible labels.', []),
 'data_model': ('Data model and ER diagram','Invoice records have an immutable ID; each invoice can have many audit events. Keep the accounting record as the financial source of truth.', []),
 'database': ('Database schema','Invoice stores validated business fields; audit events record who approved or rejected a row. Retention must be agreed before production.', [['Invoice','id UUID PK; supplier_ref TEXT; invoice_ref TEXT; amount DECIMAL; status TEXT; created_at TIMESTAMP; unique supplier_ref + invoice_ref.'],['AuditEvent','id UUID PK; invoice_id UUID FK → Invoice.id; actor_id TEXT; event TEXT; created_at TIMESTAMP; index(invoice_id, created_at).']]),
 'apis': ('REST API catalogue','Proposed internal API for the pilot; validate the final contract with implementers. No vendor API capability is assumed.', [['POST /imports','Reviewer-authenticated CSV upload; validates rows; returns import status and exception references. 400 malformed file, 403 access denied, 409 duplicate idempotency key.'],['GET /invoices','Operations role; paginated invoice status; response contains id, reference and status. 403 unauthorized, 503 store unavailable.']]),
 'integrations': ('Integration architecture','Accounting CSV exchange is proposed pending format validation. Reconcile counts and references; never retry a completed export without checking its identifier.', [['Mapping / auth','Map invoice reference and amount to the approved accounting template; only the reviewer exports.'],['Failure / source of truth','Reject format mismatches; preserve source rows and reconcile against accounting.']]),
 'estimates': ('Effort and cost estimates','Illustrative pilot: 10–20 person-days over 3–6 elapsed weeks, assuming one engineer and part-time operations review. Rates and vendor prices are unknown.', [['Validation','2–4 person-days (low confidence); confirm format and representative data.'],['Implementation / acceptance','8–16 person-days (low confidence); depends on access and reviewer availability.']]),
 'resources': ('Resource plan','Assume one delivery engineer and a part-time operations reviewer; validate availability before scheduling.', [['Engineer','Implement validation, audit and deployment; 10–20 person-days, low-confidence assumption.'],['Operations owner','Confirm rules, sample reconciliation and go-live; involvement requires validation.']]),
 'timeline': ('Timeline and milestones','Tentative elapsed duration 3–6 weeks. External access and reviewer availability are critical dependencies, so no calendar dates are committed.', [['Week 1–2','Confirm data/format and pilot acceptance criteria.'],['Week 2–5','Implement and reconcile sample imports after format approval.'],['Week 3–6','Pilot, reconcile exports and approve go-live only after failure/rollback checks.']]),
 'releases': ('Sprint and release plan','Release by validation gate rather than unsupported fixed sprint dates.', [['MVP','CSV validation, duplicate checks and exception review.'],['Pilot','Approved export, audit history and sample reconciliation.'],['Rollout','Expand only after operations accepts results and rollback is exercised.']]),
 'adoption': ('Migration, training and adoption','Train staff using sample invoices and exception cases. Reconcile any migrated open items, retain the old spreadsheet for an agreed period and review feedback weekly.', [['Measure adoption','Count completed imports, exceptions and manual re-entry before and after the pilot.']]),
 'readiness': ('Readiness assessment','Readiness remains advisory; the integration and baseline workload have not been validated.', [['Digital maturity','Developing — current spreadsheet workflow, no measured maturity baseline.'],['AI readiness','Unknown; no AI required for the selected scope.'],['Automation opportunity','Deterministic field validation and deduplication.'],['Project health','Planning stage; timeline assumptions pending confirmation.'],['Implementation readiness','Blocked on import format and representative data.'],['Solution quality','Requires reconciliation and failure/rollback testing.']]),
}


def part_fixture(schema_name):
    schema = next(s for s in PART_SCHEMAS.values() if s.__name__ == schema_name)
    from tests.fakes import deliverable_fixture
    rich = deliverable_fixture()
    rich['screens'] = [
        dict(name='Import queue',persona='Operations staff',purpose='Start an import and track progress.',controls=[
            dict(label='Queue / New import / History',kind='navigation',detail='Navigate between upload, exceptions and audit history.'),
            dict(label='Invoice CSV',kind='input',detail='Choose a structured CSV; explain required columns and maximum file size.'),
            dict(label='Validate file',kind='button',detail='Disabled while validating; show an actionable error for malformed files.'),
            dict(label='Recent imports',kind='table',detail='File, submitted by, status, accepted and rejected rows. Empty: no imports yet.')]),
        dict(name='Review exceptions',persona='Operations reviewer',purpose='Resolve errors before approving export.',controls=[
            dict(label='Invoice rows',kind='table',detail='Reference, amount, validation result and reason; highlight duplicate or missing fields.'),
            dict(label='Corrected value',kind='input',detail='Show validation feedback next to the field; retain the original value in the audit trail.'),
            dict(label='Approve export',kind='button',detail='Only reviewers can approve; block unresolved errors and show a confirmation summary.')]),
        dict(name='Import history',persona='Operations owner',purpose='Reconcile approved exports and inspect audit events.',controls=[
            dict(label='Date and status',kind='select',detail='Filter completed, failed or pending imports.'),
            dict(label='Audit events',kind='table',detail='Invoice reference, actor, action, time and export identifier. Retry failures without duplicate export.'),
            dict(label='Reconciliation',kind='metric',detail='Compare accepted source rows with exported rows; success requires matching counts and references.')]),
    ]
    rich['code_assets'][0]['content'] = '''CREATE TABLE Invoice (
  id UUID PRIMARY KEY,
  supplier_ref TEXT NOT NULL,
  invoice_ref TEXT NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL,
  UNIQUE (supplier_ref, invoice_ref)
);
CREATE TABLE AuditEvent (
  id UUID PRIMARY KEY,
  invoice_id UUID NOT NULL REFERENCES Invoice(id),
  actor_id TEXT NOT NULL,
  event TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);
CREATE INDEX audit_invoice_time ON AuditEvent(invoice_id, created_at);'''
    rich['code_assets'][1]['content'] = '''openapi: 3.0.3
info:
  title: Proposed invoice pilot API
  version: 1.0.0
security:
  - sessionCookie: []
paths:
  /invoices:
    get:
      summary: List invoice status for authorized operations staff
      parameters:
        - in: query
          name: page
          schema: {type: integer, minimum: 1}
      responses:
        '200': {description: Paginated invoice IDs, references and status}
        '403': {description: Operations role required}
        '503': {description: Audit store unavailable}
  /imports:
    post:
      summary: Validate CSV rows for an authorized reviewer
      parameters:
        - in: header
          name: Idempotency-Key
          required: true
          schema: {type: string}
      requestBody:
        required: true
        content:
          text/csv:
            schema: {type: string}
      responses:
        '200': {description: Import status and exception references}
        '400': {description: Malformed file or invalid fields}
        '403': {description: Reviewer role required}
        '409': {description: Idempotency key conflicts with another payload}
components:
  securitySchemes:
    sessionCookie:
      type: apiKey
      in: cookie
      name: session
'''
    chapters = []
    for key in sorted(schema.required_keys):
        title, narrative, rows = COPY[key]
        kinds = {'hld':['architecture'], 'future_process':['swimlane','decision_tree'], 'journeys':['workflow'], 'data_model':['er'], 'integrations':['data_flow']}.get(key, [])
        diagrams = []
        for kind in kinds:
            diagram = {**rich['diagrams'][0], 'kind':kind, 'title':title}
            if kind == 'architecture':
                diagram = {**diagram, 'nodes':[dict(id='operator',label='Operations reviewer',lane='Client',kind='component'),dict(id='importer',label='Invoice importer',lane='Application',kind='component'),dict(id='store',label='Invoice and AuditEvent',lane='Data',kind='entity')], 'edges':[dict(source='operator',target='importer',label='Upload and approve'),dict(source='importer',target='store',label='Validate and audit')]}
            elif kind == 'er':
                diagram = {**diagram, 'nodes':[dict(id='invoice',label='Invoice · id PK',lane='Invoice importer',kind='entity'),dict(id='audit',label='AuditEvent · invoice_id FK',lane='Invoice importer',kind='entity')], 'edges':[dict(source='invoice',target='audit',label='1 to 0..many; AuditEvent.invoice_id → Invoice.id')]}
            else:
                diagram = {**diagram, 'edges':[*diagram['edges'], dict(source='review',target='receive',label='Rejected: correct and resubmit')]}
            diagrams.append(diagram)
        chapters.append(dict(key=key,title=title,narrative=narrative,items=[],tables=[dict(title=title,columns=['Design aspect','Detail'],rows=rows)] if rows else [],
            applicability='applicable',basis='Synthetic fixture: proposed design based on manual invoice entry; integration, rates and dates require validation.',
            diagrams=diagrams,screens=rich['screens'] if key=='wireframes' else [],code_assets=rich['code_assets'][:1] if key=='database' else rich['code_assets'][1:] if key=='apis' else [],
            component_refs=['Invoice importer'],entity_refs=['Invoice','AuditEvent'] if key in ['database','data_model','apis'] else [],integration_refs=['Accounting CSV'] if key=='integrations' else []))
    result = dict(selected_option='balanced',chapters=chapters)
    if schema_name=='ArchitectureReport': result.update(component_names=['Invoice importer'],entity_names=['Invoice','AuditEvent'],integration_names=['Accounting CSV'])
    if schema_name=='PlanningReport': result.update(estimates=[estimate('Implementation effort','person-days',10,20),estimate('Elapsed duration','weeks',3,6),estimate('Development/setup cost','Currency to confirm'),estimate('Recurring hosting/support','Currency/month to confirm')],
        risks=[dict(risk='Accounting import format unavailable',severity='high',likelihood='unknown',impact='Blocks validated export.',mitigation='Confirm a representative CSV import before implementing the handoff.',owner='Operations owner',validation_action='Reconcile a sample with accounting.',residual_concern='Vendor changes may require remapping.')],
        unresolved_items=['Confirm accounting CSV format, retention period, baseline volume and rates.'],glossary=['Idempotency: repeating a request does not duplicate its effect.'])
    return result
