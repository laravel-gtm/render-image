# Infrastructure (AWS CDK)

This directory holds the **AWS CDK** application that deploys the render-image service: an **HTTP API** with `POST /render` backed by a **Lambda function** whose code is a **container image** built from the repository root [`Dockerfile.lambda`](../Dockerfile.lambda) (Playwright/Chromium cannot ship in a zip deployment).

The Python app entrypoint is [`app.py`](app.py), which instantiates [`RenderImageStack`](render_image_stack.py).

## Layout

| Path | Role |
|------|------|
| [`app.py`](app.py) | CDK app: creates `RenderImageStack` |
| [`render_image_stack.py`](render_image_stack.py) | Stack: `DockerImageFunction`, `HttpApi`, route `POST /render`, output `RenderApiUrl` (see **Image sources** below) |
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

## CI

Two workflows work together:

1. **[`publish-docker-image.yml`](../.github/workflows/publish-docker-image.yml)** — on push to `main`, builds `Dockerfile.lambda` and pushes `ghcr.io/<owner>/<repo>/render-image` tagged with the commit SHA and `latest`.
2. **[`deploy-aws.yml`](../.github/workflows/deploy-aws.yml)** — when **Publish Docker Image** completes successfully on `main`, checks out that commit, pulls the image from GHCR, pushes it to ECR as `render-image:<sha>`, then runs `cdk deploy` with `usePrebuiltImage` / `imageTag`. You can also run **Deploy to AWS** manually (**Actions** → **Deploy to AWS** → **Run workflow**) and pass an existing `image_tag` (full SHA) that is already in GHCR.

Configure the `AWS_DEPLOY_ROLE_ARN` secret and optional `AWS_REGION` variable; see the **GitHub Actions deploy** section in the root [README](../README.md). The account must already be **bootstrapped** in that Region before the first deploy workflow run.

## IAM for GitHub Actions

See [`iam/github-actions-trust-policy.json`](iam/github-actions-trust-policy.json) and [`iam/github-actions-deploy-policy.json`](iam/github-actions-deploy-policy.json). Edit placeholders (GitHub org/repo, Region, account if not committed) before attaching them to the role assumed by the workflow.
