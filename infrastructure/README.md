# Infrastructure (AWS CDK)

This directory holds the **AWS CDK** application that deploys the render-image service: an **HTTP API** with `POST /render` backed by a **Lambda function** whose code is a **container image** built from the repository root [`Dockerfile.lambda`](../Dockerfile.lambda) (Playwright/Chromium cannot ship in a zip deployment).

The Python app entrypoint is [`app.py`](app.py), which instantiates [`RenderImageStack`](render_image_stack.py).

## Layout

| Path | Role |
|------|------|
| [`app.py`](app.py) | CDK app: creates `RenderImageStack` |
| [`render_image_stack.py`](render_image_stack.py) | Stack: `DockerImageFunction`, `HttpApi`, route `POST /render`, output `RenderApiUrl`. Optional custom domain via Route 53 + ACM (see **Custom domain** below) |
| [`cdk.json`](cdk.json) | CDK config; `app` runs `uv run python app.py` |
| [`pyproject.toml`](pyproject.toml) | `aws-cdk-lib`, `constructs` (managed by `uv`) |
| [`iam/`](iam/) | Example IAM policies for GitHub Actions OIDC deploy role (trust + permissions) |

Synth output goes to `cdk.out/` (gitignored).

## Prerequisites

- **AWS account** and credentials (`aws configure` or environment variables)
- **Docker** (for `cdk deploy` so CDK can build and push the Lambda container image)
- **Node.js 24** (for `npx aws-cdk`)
- **[uv](https://docs.astral.sh/uv/)** (Python package manager; manages Python 3.14 automatically)

## One-time: bootstrap

Per **account** and **Region**, CDK needs tooling buckets, ECR, and IAM roles. Run once (replace account and region):

```bash
npx aws-cdk@^2 bootstrap aws://ACCOUNT_ID/REGION
```

Use the same Region you deploy to (for example `us-east-1`).

## Setup

From this directory:

```bash
uv sync
```

## Image sources

`RenderImageStack` chooses how the Lambda container image is supplied:

| Mode | When | Behavior |
|------|------|----------|
| **Local / default** | No `usePrebuiltImage` context | Builds from repo root [`Dockerfile.lambda`](../Dockerfile.lambda) during `cdk deploy` (Docker required). |
| **Prebuilt (CI)** | `-c usePrebuiltImage=true -c imageTag=<git-sha>` | Uses an image already in Amazon **ECR** repository `render-image` at that tag. CI builds once, pushes to **GitHub Container Registry (GHCR)**, copies the same image to ECR, then deploys. |

For prebuilt mode, create the ECR repository once if it does not exist (the deploy workflow runs `aws ecr create-repository` when needed). The image in ECR must match what [`Dockerfile.lambda`](../Dockerfile.lambda) produces (same handler and layout).

## Synth and deploy

**Default (build during deploy):**

```bash
export AWS_REGION=your-region   # if not already set
npx aws-cdk@^2 synth
npx aws-cdk@^2 deploy --require-approval never
```

**Prebuilt image in ECR** (for example after CI copied GHCR → ECR):

```bash
npx aws-cdk@^2 deploy --require-approval never \
  -c usePrebuiltImage=true \
  -c "imageTag=FULL_GIT_SHA"
```

After a successful deploy, CloudFormation prints **RenderApiUrl** (HTTP API base URL). Send JSON to `{RenderApiUrl}/render` (see the root [README](../README.md) for the request body).

**With a custom domain:**

```bash
npx aws-cdk@^2 deploy --require-approval never \
  -c hostedZoneName=laravel-gtm.cloud \
  -c certificateArn=arn:aws:acm:us-east-1:123456789012:certificate/abc-def-123
```

This creates an API Gateway custom domain `api-{region}.{zone}`, an API mapping, and a Route 53 A record alias. Both context values are required; if either is omitted, the custom domain is skipped and the stack behaves as before.

## Custom domain

The stack optionally attaches a custom domain to the HTTP API for stable internal (VPC) access. The FQDN follows the pattern `api-{region}.{zone}` (e.g. `api-us-east-1.laravel-gtm.cloud`).

**Prerequisites (one-time, manual):**

1. **Route 53 private hosted zone** — create a private hosted zone for your domain (e.g. `laravel-gtm.cloud`) and associate it with the VPC(s) that will call the API.
2. **ACM certificate** — request a certificate in the **same region** as the deployment for the FQDN `api-{region}.{zone}`. Validate via DNS (add the CNAME validation record in your public DNS provider, e.g. Cloudflare). Wait for status `Issued`.

**CDK context flags:**

| Flag | Required | Description |
|------|----------|-------------|
| `hostedZoneName` | When using custom domain | Route 53 private hosted zone name (e.g. `laravel-gtm.cloud`) |
| `certificateArn` | When using custom domain | ARN of the ACM certificate for `api-{region}.{zone}` |

When these flags are set, `app.py` pins the stack to a concrete AWS environment (`CDK_DEFAULT_ACCOUNT` / `CDK_DEFAULT_REGION`) because `HostedZone.from_lookup()` makes API calls at synth time. When unset, the stack remains environment-agnostic.

**Resources created:**

- `AWS::ApiGatewayV2::DomainName` — the custom domain on API Gateway
- `AWS::ApiGatewayV2::ApiMapping` — maps the HTTP API to the custom domain
- `AWS::Route53::RecordSet` — A record alias pointing at the API Gateway regional domain
- `CustomDomainUrl` CloudFormation output (`https://api-{region}.{zone}`)

## CI

Two workflows work together:

1. **[`publish-docker-image.yml`](../.github/workflows/publish-docker-image.yml)** — on push to `main`, builds `Dockerfile.lambda` and pushes `ghcr.io/<owner>/<repo>/render-image` tagged with the commit SHA and `latest`.
2. **[`deploy-aws.yml`](../.github/workflows/deploy-aws.yml)** — when **Publish Docker Image** completes successfully on `main`, checks out that commit, pulls the image from GHCR, pushes it to ECR as `render-image:<sha>`, then runs `cdk deploy` with `usePrebuiltImage` / `imageTag`. You can also run **Deploy to AWS** manually (**Actions** → **Deploy to AWS** → **Run workflow**) and pass an existing `image_tag` (full SHA) that is already in GHCR.

Configure the `AWS_DEPLOY_ROLE_ARN` secret and optional `AWS_REGION` variable; see the **GitHub Actions deploy** section in the root [README](../README.md). The account must already be **bootstrapped** in that Region before the first deploy workflow run.

## IAM for GitHub Actions

See [`iam/github-actions-trust-policy.json`](iam/github-actions-trust-policy.json) and [`iam/github-actions-deploy-policy.json`](iam/github-actions-deploy-policy.json). Edit placeholders (GitHub org/repo, Region, account if not committed) before attaching them to the role assumed by the workflow.

The deploy policy includes Route 53 permissions (for hosted zone lookup during synth and record management during deploy) and ACM read permissions (for the workflow's certificate discovery step). These are only exercised when the `HOSTED_ZONE_NAME` variable is set.
