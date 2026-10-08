"""Idempotent additive indexes. No project, application or credit data is deleted."""
def upgrade(db):
    db.application_generation_runs.create_index([('project_id', 1), ('updated_at', -1)])
    db.application_generation_steps.create_index([('run_id', 1), ('status', 1)])
    db.application_generation_steps.create_index('project_id')
    db.application_syncs.create_index([('project_id', 1), ('created_at', -1)])
    db.application_blueprints.create_index([('project_id',1),('version',-1)],unique=True)
    db.application_artifacts.create_index([('project_id',1),('created_at',-1)])
    db.native_workers.create_index('heartbeat_at',expireAfterSeconds=86400)
    db.credit_purchases.create_index('provider_id', unique=True, sparse=True)
    db.credit_purchases.create_index([('actor', 1), ('mode', 1), ('created_at', -1)])
    db.builder_jobs.create_index([('status', 1), ('available_at', 1), ('lease_until', 1)])
    db.worker_health.create_index('heartbeat_at', expireAfterSeconds=86400)
    db.builder_jobs.create_index([('project_id', 1), ('status', 1)])
    db.security_events.create_index([('actor', 1), ('created_at', -1)])
    db.subscription_orders.create_index('provider_id', sparse=True)
    db.subscription_payments.create_index([('actor', 1), ('created_at', -1)])
    db.application_specs.create_index([('project_id', 1), ('version', -1)], unique=True)
    db.application_builds.create_index([('project_id', 1), ('request_id', 1)], unique=True)
    db.application_deployments.create_index([('project_id', 1), ('created_at', -1)])
    db.application_previews.create_index([('project_id', 1), ('status', 1)])
    db.builder_audit.create_index('created_at')
    # A new unique-index conflict must be investigated, never auto-deduplicated.
    db.schema_migrations.update_one({'_id': '20260924_application_builder'}, {'$setOnInsert': {
        'description': 'Application versions, build idempotency, deployments, previews and billing audit indexes'}}, upsert=True)


if __name__ == '__main__':
    from app.repositories.store import get_store
    upgrade(get_store().db)
    print('Application builder indexes are ready. Existing data was preserved.')
