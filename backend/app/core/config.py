from pathlib import Path
from functools import lru_cache
from typing import Literal
from decimal import Decimal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / '.env', extra='ignore')
    gemini_api_key: str = ''
    gemini_api_keys: str = ''
    gemini_model: str = 'gemini-2.5-flash'
    gemini_thinking_level: Literal['minimal', 'low', 'medium', 'high'] | None = None
    gemini_effort: Literal['instant', 'low', 'medium', 'high'] = 'low'
    # Groq is reserved for prototype/application building.
    groq_api_key: str = ''
    groq_api_keys: str = ''
    groq_model: str = 'openai/gpt-oss-120b'
    groq_max_completion_tokens: int = Field(default=16000, ge=256, le=32768)
    groq_cooldown_wait_seconds: int = Field(default=120, ge=0, le=600)
    groq_context_window: int = Field(default=131072, ge=1024)
    groq_model_output_limit: int = Field(default=65536, ge=256)
    groq_tokens_per_minute: int = Field(default=8000, ge=1024)
    groq_stage_output_tokens: int = Field(default=2048, ge=512, le=16000)
    # App building may use the Gemini pool when Groq cannot serve a stage.
    builder_gemini_fallback: bool = True
    mongodb_uri: str = ''
    mongodb_database: str = 'shift_ai'
    # Atlas discovery/TLS and election recovery can exceed five seconds on Wi-Fi.
    mongodb_server_selection_timeout_ms: int = Field(default=20000, ge=1000, le=60000)
    mongodb_connect_timeout_ms: int = Field(default=15000, ge=1000, le=60000)
    mongodb_socket_timeout_ms: int = Field(default=30000, ge=1000, le=120000)
    # 3000/3001 serve the website; 3100 serves the phone app frontend.
    cors_origins: str = 'http://localhost:3000,http://localhost:3001,http://localhost:3100'
    lan_access: bool = False
    max_upload_mb: int = 15
    google_client_id: str = ''
    session_secret: str = ''
    cookie_secure: bool = False
    allow_local_access: bool = False
    vector_search_enabled: bool = False
    vector_index_name: str = 'document_embeddings'
    embedding_model: str = 'gemini-embedding-001'
    app_base_url: str = 'http://localhost:3000'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    smtp_from_name: str = 'shift.AI'
    smtp_starttls: bool = True
    password_reset_minutes: int = 30
    # Without SMTP, show the reset link only to loopback callers so local setup can still finish a reset.
    password_reset_local_link: bool = True
    # JSON map: project ID -> {service_id, image_repository}. Server controlled only.
    render_targets_json: str = '{}'
    render_api_key: str = ''
    # Preview URLs are loopback-only and intended for the machine running Docker.
    application_preview_enabled: bool = True
    # Generated applications use trusted templates; containers never receive platform secrets.
    builder_enabled: bool = True
    builder_timeout_seconds: int = 180
    builder_initial_credits: int = 100
    builder_build_cost: int = 10
    vercel_token: str = ''
    vercel_team_id: str = ''
    builder_admin_ids: str = ''
    # Test checkout is deliberately separate from enabling real money payments.
    razorpay_mode: Literal['test', 'live'] = 'test'
    razorpay_live_enabled: bool = False
    razorpay_key_id: str = ''
    razorpay_key_secret: str = ''
    razorpay_webhook_secret: str = ''
    razorpay_plans_json: str = '{}'
    # Presentation catalog for the pricing page. Empty uses the built-in default.
    subscription_catalog_json: str = ''
    razorpay_currency: Literal['INR'] = 'INR'
    razorpay_business_name: str = Field(default='shift.AI', min_length=1, max_length=100)
    razorpay_minimum_amount: Decimal = Field(default=Decimal('1.00'), gt=0, le=1000000)
    razorpay_credit_packs_enabled: bool = False
    razorpay_credit_pack_amount: int = Field(default=9900, ge=100, le=100000000)
    razorpay_credit_pack_credits: int = Field(default=100, ge=1, le=100000)
    builder_job_mode: Literal['durable', 'background'] = 'durable'
    worker_embedded: bool = True
    portable_preview_origin: str = 'http://localhost:8000'
    native_worker_targets: str = ''
    native_artifact_dir: str = '.local/application-artifacts'
    native_build_timeout: int = Field(default=1200, ge=60, le=3600)
    native_dependency_network: bool = False
    native_apple_team: str = ''
    preview_public_origin: str = ''
    api_public_origin: str = ''
    document_converter_image: str = 'shift-document-converter:1'
    document_ocr_languages: str = 'eng+hin+guj'
    oidc_issuer: str = ''
    oidc_client_id: str = ''
    oidc_client_secret: str = ''
    oidc_redirect_uri: str = ''
    oidc_email_domains: str = ''

    # ---- Generated-application data plane -------------------------------------
    # Generated applications never touch the platform database. Their records live
    # on a separate Atlas cluster, one database and one scoped user per application.
    app_atlas_uri: str = ''
    app_atlas_database_prefix: str = 'shift_app_'
    # Atlas Administration API: required to create the per-application database user.
    # A connection string cannot create users, so these are separate credentials.
    # Either a service account (OAuth client credentials) or a legacy digest key pair.
    atlas_service_client_id: str = ''
    atlas_service_client_secret: str = ''
    atlas_public_key: str = ''
    atlas_private_key: str = ''
    atlas_project_id: str = ''
    atlas_cluster_name: str = ''
    # Generated source is delivered to Render/Vercel through a GitHub App install.
    # The App private key and installation ID are what mint repository tokens;
    # the OAuth client pair alone cannot create or push repositories.
    github_app_id: str = ''
    github_client_id: str = ''
    github_client_secret: str = ''
    github_app_private_key: str = ''
    github_app_private_key_path: str = ''
    github_installation_id: str = ''
    github_owner: str = ''
    # An App installation token cannot create repositories on a personal account,
    # so repository creation there needs a user-authorised token.
    github_pat: str = ''
    # Render workspace that owns generated backend services.
    render_owner_id: str = ''
    render_region: str = 'singapore'
    render_plan: str = 'free'
    # One-click deployment. The OAuth callback must be registered on the GitHub App.
    deploy_callback_origin: str = 'http://localhost:8000'
    deploy_poll_seconds: int = Field(default=10, ge=1, le=120)
    deploy_timeout_minutes: int = Field(default=25, ge=5, le=120)

    @property
    def gemini_keys(self):
        # Keep the existing primary key first; ignore blank and duplicate entries.
        entries = [self.gemini_api_key, *self.gemini_api_keys.replace('\n', ',').split(',')]
        return list(dict.fromkeys(key.strip() for key in entries if key.strip()))

    @property
    def groq_keys(self):
        entries = [self.groq_api_key, *self.groq_api_keys.replace('\n', ',').split(',')]
        return list(dict.fromkeys(key.strip() for key in entries if key.strip()))

    @property
    def origins(self):
        origins = [s.strip() for s in self.cors_origins.split(',') if s.strip()]
        if self.lan_access:
            from app.lan import lan_origins
            origins += lan_origins()
        return list(dict.fromkeys(origins))


@lru_cache
def get_settings():
    return Settings()
