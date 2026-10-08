# Additional capabilities and setup

The continuation implements the six requested feature areas. Deployment of the
existing site is already handled by the owner. These instructions cover the new
optional services and credentials; no external payment, message or live release
was submitted during verification.

## Razorpay one-time test credit purchases

`/billing` supports a one-time INR 99 purchase of 100 credits, with no recurring
mandate. The current local backend has test credentials and credit packs enabled;
live payments remain disabled. Secrets stay in the backend environment and are
not included in source files or returned to the browser. Other installations need:

```dotenv
RAZORPAY_MODE=test
RAZORPAY_LIVE_ENABLED=false
RAZORPAY_KEY_ID=rzp_test_REPLACE
RAZORPAY_KEY_SECRET=
RAZORPAY_CREDIT_PACKS_ENABLED=true
RAZORPAY_CREDIT_PACK_AMOUNT=9900
RAZORPAY_CREDIT_PACK_CREDITS=100
RAZORPAY_WEBHOOK_SECRET=
```

Amounts are in paise. The backend saves the price and credit quantity before
creating a Razorpay Order, and rejects stale browser quotes. Checkout verifies
the signature against the saved order ID and checks ownership, captured payment,
currency and the fully paid order before granting credits once per order.
An authorized payment alone does not grant credits. Configure automatic payment
capture in Razorpay, or capture authorized test payments in its dashboard.

Use `https://YOUR_API_HOST/api/billing/razorpay/webhook` with `payment.captured`
and `order.paid` events and a matching webhook secret. Both events recover the
saved purchase even when settlement arrives before the create response is saved.
The billing page's **Refresh payment status** action also reconciles a missed
callback or webhook. Dashboard webhook delivery needs a publicly reachable API;
local browser callbacks and manual refresh can verify payments without it.

Retries of the same purchase request reuse the existing order. An interrupted
creation is looked up by its receipt instead of blindly issuing another order.
One-time purchases do not require `RAZORPAY_PLANS_JSON`; recurring subscriptions
remain unavailable until plans are configured. Test purchases grant credits to
the same platform credit account used by application generation.

Verification: 201 existing backend tests, eight temporary payment checks, ten
desktop/mobile browser scenarios, an isolated production build with TypeScript,
and ESLint passed. Browser checkout and payment settlement used substitutes;
the configured test credentials also passed a read-only Razorpay Orders API
request. No payment was submitted during this continuation. The existing 1,000-entry
credit ledger bound and manual post-grant refund/chargeback reconciliation apply
to these purchases as well. Signature and order integration follow the official
[Razorpay payment verification](https://github.com/razorpay/razorpay-node/blob/master/documents/paymentVerfication.md)
and [Orders API](https://github.com/razorpay/razorpay-node/blob/master/documents/order.md) documentation.

## Razorpay test subscriptions

Recurring checkout shows setup pending until test keys, a webhook secret and
plans are configured. Defaults are `RAZORPAY_MODE=test` and
`RAZORPAY_LIVE_ENABLED=false`. Keep those values.

Add these **backend-only** values later:

```dotenv
RAZORPAY_MODE=test
RAZORPAY_LIVE_ENABLED=false
RAZORPAY_KEY_ID=rzp_test_REPLACE
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
RAZORPAY_PLANS_JSON={"starter":{"name":"Starter","plan_id":"plan_REPLACE","credits":100}}
```

Create the recurring INR plan in the Razorpay test dashboard. The backend fetches
the actual price, interval and period; it does not trust amounts from the browser.
Each subscription currently uses 12 billing cycles. Credits are per captured paid
invoice, not per mandate authorization. Test payments issue test-mode subscription
credits to the same platform credit account used for generation.

Configure the test webhook URL as
`https://YOUR_API_HOST/api/billing/razorpay/webhook`, using the same webhook secret.
Subscribe to subscription lifecycle events, including `subscription.charged`.
Webhook handling checks the raw-body signature and fetches current provider state.
Checkout verification uses the server-stored subscription ID. Duplicate deliveries
and browser refreshes cannot grant the same payment twice. “Refresh payment status”
reconciles missed events; uncertain subscription creation is reconciled before a
second subscription can be created. An unconfirmed creation that cannot be found
in the first 500 provider subscriptions needs operator investigation.

Cancellation requests the end of the current billing cycle. Provider restrictions
on cancelling an unactivated mandate can require dashboard intervention. Refunds
or chargebacks after credits were granted require operator credit reconciliation.
The existing account ledger still has a 1,000-entry bound; it is not an unlimited
financial ledger. Invoice and reconciliation queries are bounded to 100 invoices.

No real recurring Razorpay checkout was executed; recurring plan configuration
is pending. Signature, ownership, deduplication and reconciliation were tested with
a deterministic provider substitute. Integration follows the official
[Razorpay subscription guide](https://razorpay.com/docs/payments/subscriptions/integration-guide/)
and [webhook validation guide](https://razorpay.com/docs/webhooks/validate-test/).

## Business calculations, public pages and integrations

Approved specifications can contain `entity.logic` with a restricted
`calculate(record)` function, output field names and at least two frozen examples.
The runtime computes outputs on the server. Use `number` for Decimal arithmetic
and `money` for two-decimal rounding. Payroll rates and rules must be provided and
reviewed; the generator does not claim legal payroll compliance. Arbitrary imports,
file/network access and unrestricted server code are not supported.

Functions execute in bounded subprocesses inside the generated application
container. Failed acceptance tests can trigger at most two model repair attempts.
Only `business_functions.json` changes; approved examples, roles, schema and trusted
runtime stay fixed. ZIP exports include the complete repair history. Runtime tests
must pass before a build becomes ready. Passing examples are not a proof for every
possible input, so review repaired business code before production use.

`public_pages` creates responsive escaped HTML at `/site/<slug>`, with the first
page at `/`; the authenticated app remains at `/workspace`. Public copy, navigation
and contact email are supported. This is not a general CMS or public upload service.

`entity.integrations` declares explicit actions, allowed fields and roles. Generated
buttons ask before sending and enqueue a durable SQLite outbox. Configure
`INTEGRATION_<ACTION_NAME>_URL` and optional `_TOKEN` in the generated app's process
environment. Only public HTTPS port 443 is permitted; addresses are checked and
pinned, redirects are rejected, and secrets never enter the generated specification.
The receiver must honor `Idempotency-Key`: delivery is at least once, up to five
attempts. Delivery status is available in the app. Docker previews cannot reach
external services. Provider-specific OAuth adapters are separate implementation work.

## Durable builder jobs and remote preview

Builder planning, generation and Render/Vercel submissions now use Mongo jobs by
default. The API starts an embedded worker for compatibility. A dedicated process
can instead run:

```powershell
# API environment: WORKER_EMBEDDED=false, BUILDER_JOB_MODE=durable
cd backend
.venv/Scripts/python.exe -m app.worker
```

Workers share MongoDB, platform configuration and access to the same Docker daemon
and image store. Jobs have leases, heartbeats, bounded retries and interrupted-job
recovery. Work is at least once; this is not a claim of exactly-once distributed
execution or high availability. External submissions with an uncertain result are
not blindly repeated. Existing discovery/analysis tasks retain their original
execution path. `/account` shows worker/job status to configured administrators.

For remote previews, configure a dedicated HTTPS hostname distinct from both
frontend and API hosts:

```dotenv
API_PUBLIC_ORIGIN=https://api.example.com
PREVIEW_PUBLIC_ORIGIN=https://preview.example.net
```

Run `uvicorn app.preview_gateway:app --host 127.0.0.1 --port 8090` behind TLS on the
Docker host. This separate process needs the same MongoDB and SESSION_SECRET and
access to the generated containers' loopback relay ports. Do not reverse-proxy this
application under the platform hostname. Configure access logs to omit ticket query
strings. Studio generates one-use, 60-second links; a host-only secure session cookie
then permits access until the preview expires. A new link can be requested from
the preview panel. Each preview has a 15-minute lifetime and temporary data.
Platform cookies are not forwarded into generated applications.

Gateway authentication, replay rejection and real Docker proxy CRUD were verified
locally. Public DNS/TLS and remote-host routing still need operator configuration.

## Legacy Office documents and OCR

Build the converter image on each Docker worker host:

```powershell
docker build -t shift-document-converter:1 backend/containers/documents
```

The image has been built and tested on this machine. DOC/PPT conversion uses
LibreOffice; scanned PDF and PNG/JPEG/TIFF use Tesseract. The converter has no network,
no platform secrets, a read-only root filesystem, bounded memory/CPU/time and
temporary storage. Defaults use `DOCUMENT_OCR_LANGUAGES=eng+hin+guj`; installed packs
also include `spa`, `fra`, `deu`, `ara`. PDFs are limited to 300 pages, at most 30 OCR
pages per conversion, and 500,000 extracted characters. Large scans should be split.
OCR accuracy depends on image quality. Encrypted or malformed files return an error.

## Localization and enterprise identity

Generated app shared labels and selected error messages are translated, cached and
frozen into the approved draft alongside localized domain labels. The existing
20-language selection remains available. New translations require human review;
some dynamic messages and administrative interfaces remain English.

`/account` supports password-confirmed TOTP enrollment, encrypted factor secrets,
one-use recovery codes, replay prevention, disabling MFA and revoking other password
sessions. MFA applies to password accounts; external-provider factors stay with the
provider. Rotating SESSION_SECRET also affects encrypted TOTP secrets, so plan a
controlled factor re-enrollment when rotating it.

Configure organization SSO with `OIDC_ISSUER`, `OIDC_CLIENT_ID`,
`OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI` and optional `OIDC_EMAIL_DOMAINS`.
The redirect URI is `https://YOUR_API_HOST/api/auth/sso/callback`.
Use `COOKIE_SECURE=true` with HTTPS. Supported providers must offer OIDC discovery,
RS256 identity tokens, PKCE S256, `client_secret_basic`, and verified email claims.
The login page shows organization sign-in only after configuration. State and nonce
are browser-bound and single-use; signature, issuer, audience, expiry and domain are
validated. SSO accounts are separate identities and are never silently linked to
password accounts by email. Provider integration follows
[OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html) and
[PyJWT validation documentation](https://pyjwt.readthedocs.io/en/stable/usage.html).

`BUILDER_ADMIN_IDS` explicitly grants account administration, security-event viewing
and worker visibility. Password and OIDC accounts can be disabled with session
revocation. Existing Google accounts retain their existing sign-in path. This does
not implement SCIM/SAML, mandatory organization-wide SSO, immutable audit storage,
HA, disaster-recovery drills or load certification. Real identity-provider acceptance
requires that provider's configuration; local verification used signed RSA tokens.
