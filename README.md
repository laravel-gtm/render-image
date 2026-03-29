# Render Image

Framework-agnostic Python PDF renderer designed to be called from Laravel via a
custom Spatie Laravel PDF driver, with one shared rendering core across:

- AWS Lambda + API Gateway
- Container service runtime
- Cloudflare Worker proxy flow

## What this implements

- A typed rendering contract (`RenderRequest`) that maps to common Spatie options:
  - `html`
  - `format` OR `paper_size`
  - `margins`
  - `orientation`
  - `header_html` / `footer_html`
- A shared Playwright/Chromium renderer:
  - `render_pdf(request)` (sync)
  - `render_pdf_async(request)` (async)
- Thin adapters:
  - `render_image.adapters.aws_lambda.lambda_handler`
  - `render_image.adapters.container.handle_payload`
  - `render_image.adapters.cloudflare.handle_worker_payload`

## Install

```bash
uv sync
uv run playwright install chromium
```

## Request contract

Minimal JSON payload:

```json
{
  "html": "<html><body><h1>Invoice</h1></body></html>"
}
```

Extended payload example:

```json
{
  "html": "<html><body><h1>Invoice #123</h1></body></html>",
  "format": "a4",
  "margins": { "top": "10mm", "right": "10mm", "bottom": "12mm", "left": "10mm" },
  "orientation": "portrait",
  "header_html": "<div style='font-size:10px;'>Header</div>",
  "footer_html": "<div style='font-size:10px;'>Footer</div>",
  "timeout_ms": 30000,
  "filename": "invoice-123.pdf",
  "metadata": { "invoice_id": "123" }
}
```

Notes:

- Use `format` (for example `a4`, `letter`) or `paper_size` (`width` and `height`), not both.
- Validation/auth should happen at API Gateway/edge service; this module still performs defensive validation.

## Runtime usage

### Container/CLI

```bash
echo '{"html":"<h1>Hello</h1>","format":"a4"}' | uv run python main.py
```

Outputs JSON that includes `pdf_base64`.

### AWS Lambda

Use handler:

```python
from render_image.adapters.aws_lambda import lambda_handler
```

Expected input: API Gateway proxy event with a JSON body.  
Output: API Gateway response with base64 encoded PDF body and `application/pdf`.

### Deploy to AWS (CDK)

The [infrastructure/](infrastructure/) directory defines an **HTTP API** (`POST /render`) backed by a **Lambda function** packaged as a **container image** ([Dockerfile.lambda](Dockerfile.lambda)), because Playwright and Chromium exceed Lambda zip size limits.

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) (running locally for `cdk deploy` to build and push the image), [Node.js](https://nodejs.org/) (for the `cdk` CLI, for example `npx aws-cdk`), and an AWS account with credentials configured (`aws configure` or environment variables).

From the repository root:

```bash
cd infrastructure
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate.bat
pip install -r requirements.txt
```

One-time per account and Region:

```bash
npx aws-cdk bootstrap aws://ACCOUNT_ID/REGION
```

Deploy:

```bash
npx aws-cdk deploy
```

After deploy, note the **RenderApiUrl** output (API base URL). Invoke the renderer:

```bash
curl -sS -X POST "${RENDER_API_URL}/render" \
  -H "Content-Type: application/json" \
  -d '{"html":"<html><body><h1>Hello</h1></body></html>","format":"a4"}' \
  --output /tmp/out.pdf
```

`cdk.json` runs the app with `.venv/bin/python app.py`; on Windows, change the `app` entry in [infrastructure/cdk.json](infrastructure/cdk.json) to `.venv\\Scripts\\python.exe app.py` or activate the venv and use a shell where `python` resolves to that interpreter.

**Limits:** API Gateway and Lambda impose payload and response size limits (order of megabytes). Very large HTML or PDFs may need a different integration (for example async jobs and object storage).

### GitHub Actions deploy (push to `main`)

CI uses two workflows:

1. **[`.github/workflows/publish-docker-image.yml`](.github/workflows/publish-docker-image.yml)** — builds [`Dockerfile.lambda`](Dockerfile.lambda) and pushes to **GitHub Container Registry** at `ghcr.io/<owner>/<repo>/render-image` (tags: full git SHA and `latest`).
2. **[`.github/workflows/deploy-aws.yml`](.github/workflows/deploy-aws.yml)** — runs **after** a successful publish on `main`: pulls that image from GHCR, pushes it to Amazon **ECR** (`render-image:<sha>`), then `cdk deploy` with a **prebuilt** image (see [infrastructure/README.md](infrastructure/README.md)). Deploy does not rebuild the Docker image; it reuses the GHCR artifact.

The deploy job assumes an IAM role via [OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services). **Bootstrap** the target account and Region once (see above) before the first deploy workflow run; the attached IAM policy expects the default CDK asset bucket and bootstrap roles to already exist. You can **re-run** deploy for an older image with **Actions → Deploy to AWS → Run workflow** and the `image_tag` input (full SHA present in GHCR).

**Repository settings**

| Type | Name | Required | Default | Description |
|------|------|----------|---------|-------------|
| Secret | `AWS_DEPLOY_ROLE_ARN` | Yes | — | ARN of the IAM role GitHub may assume (e.g. `arn:aws:iam::123456789012:role/github-actions-render-image-deploy`) |
| Variable | `AWS_REGION` | Yes | — | AWS region to deploy into (e.g. `us-east-1`) |
| Variable | `IMAGE_NAME` | No | `render-image` | ECR repository and GHCR image name |
| Variable | `STACK_NAME` | No | `RenderImageStack` | CloudFormation stack name |
| Variable | `LAMBDA_MEMORY_MB` | No | `3008` | Lambda function memory in MB |
| Variable | `LAMBDA_TIMEOUT_SECONDS` | No | `29` | Lambda function timeout in seconds |
| Variable | `HOSTED_ZONE_NAME` | No | — | Route 53 private hosted zone for custom domain (e.g. `laravel-gtm.cloud`). When set, the deploy workflow looks up an ACM certificate for `api-{region}.{zone}` and attaches it to the HTTP API |

**AWS: OIDC provider (once per account)**

If you do not already use GitHub’s OIDC provider in the account, create it (thumbprints can change; use [GitHub’s current instructions](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services#adding-the-identity-provider-to-aws)):

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list <GITHUB_THUMBPRINTS>
```

**AWS: deployment role**

1. Copy [infrastructure/iam/github-actions-trust-policy.json](infrastructure/iam/github-actions-trust-policy.json) and replace `YOUR_ACCOUNT_ID`, `YOUR_GITHUB_ORG`, and `YOUR_GITHUB_REPO`. Use this JSON as the role’s **trust policy** when you create the role.
2. Copy [infrastructure/iam/github-actions-deploy-policy.json](infrastructure/iam/github-actions-deploy-policy.json) and replace `YOUR_ACCOUNT_ID` and `YOUR_REGION` everywhere (including the S3 bootstrap asset bucket name). Attach the result as an **inline or managed customer policy** on the same role.
3. Policies target the default CDK bootstrap qualifier `hnb659fds`. If you use a custom bootstrap qualifier, widen ARNs (for example `cdk-*` S3 bucket and IAM role patterns) to match your bootstrap stack.

The deploy policy grants `sts:AssumeRole` on `cdk-hnb659fds-*` bootstrap roles (for container asset publishing), CloudFormation, the CDK asset S3 bucket, ECR, Lambda, API Gateway, Logs, EventBridge rules used by CDK, IAM role management in your account for stack-created roles, Route 53 (hosted zone lookup and record management), and ACM (certificate discovery). Tighten resources if your organization requires least privilege.

**Custom domain (optional)**

You can give the HTTP API a stable hostname instead of the auto-generated `execute-api` URL. The domain follows the pattern `api-{region}.{zone}` (e.g. `api-us-east-1.laravel-gtm.cloud`).

Prerequisites:

1. **Route 53 private hosted zone** — create (or import) a private hosted zone for your domain (e.g. `laravel-gtm.cloud`) and associate it with the VPC(s) that will call the API.
2. **ACM certificate** — request a certificate in the **same region** as the deployment for the FQDN `api-{region}.{zone}` (e.g. `api-us-east-1.laravel-gtm.cloud`). Validate the certificate via DNS (Cloudflare or whichever provider hosts the public zone for validation records). The certificate must be in the `Issued` state before deploying.
3. **Set the `HOSTED_ZONE_NAME` variable** in your GitHub repository settings (e.g. `laravel-gtm.cloud`). The deploy workflow will automatically discover the matching ACM certificate ARN and pass it to CDK.

When deployed with the custom domain, CloudFormation outputs both `RenderApiUrl` (the default endpoint) and `CustomDomainUrl` (`https://api-{region}.{zone}`). From within the associated VPC, the custom domain resolves to the API Gateway.

### Cloudflare Worker proxy flow

Workers should validate/authenticate and forward a JSON payload to your Python
origin. Keep the payload under `render_request` or send the request object as-is.

Python entrypoint:

```python
from render_image.adapters.cloudflare import handle_worker_payload
```
