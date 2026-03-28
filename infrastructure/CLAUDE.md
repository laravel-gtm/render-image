# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the `infrastructure/` directory.

```bash
uv sync                                                # Install dependencies
uv run ruff check .                                    # Lint
uv run ruff format .                                   # Format
uv run ty check --project .                            # Type check (--project . scopes to this subproject)

npx aws-cdk@^2 synth                               # Synthesize CloudFormation
npx aws-cdk@^2 deploy --require-approval never     # Deploy (local Docker build)
npx aws-cdk@^2 deploy --require-approval never \   # Deploy prebuilt image from ECR
  -c usePrebuiltImage=true -c "imageTag=FULL_GIT_SHA"
npx aws-cdk@^2 bootstrap aws://ACCOUNT_ID/REGION   # One-time per account/region
```

## Architecture

AWS CDK app (Python, `aws-cdk-lib`) deploying the render-image service as a Lambda container behind an HTTP API Gateway.

- `app.py` — CDK entrypoint; instantiates `RenderImageStack`
- `render_image_stack.py` — Single stack: `DockerImageFunction` (3008 MB, 29s timeout, x86_64) + `HttpApi` with `POST /render` route. Outputs `RenderApiUrl`
- `iam/` — Example IAM policies for GitHub Actions OIDC deploy role

## Key Constraints

- Python >=3.14, managed with `uv` (same as the main project)
- `cdk.json` runs the app via `uv run python app.py`
- Two image modes controlled by CDK context flags:
  - **Default**: builds from repo root `Dockerfile.lambda` during deploy (requires Docker)
  - **Prebuilt**: `-c usePrebuiltImage=true -c imageTag=<sha>` pulls from ECR repo `render-image`; `imageTag` is required or deploy raises `ValueError`
- ECR repository name is hardcoded as `render-image` in `render_image_stack.py`

## CI Pipeline

1. `publish-docker-image.yml` — builds `Dockerfile.lambda`, pushes to GHCR tagged with commit SHA + `latest`
2. `deploy-aws.yml` — triggered on successful publish; copies GHCR image to ECR, runs `cdk deploy` with prebuilt image context. Can also be triggered manually with an existing `image_tag`
- Requires `AWS_DEPLOY_ROLE_ARN` secret and optional `AWS_REGION` variable
