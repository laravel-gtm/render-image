from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_ecr as ecr,
    aws_lambda as lambda_,
)
from constructs import Construct

# ECR repository name used by CI: image is pushed here after copying from GHCR.
ECR_REPOSITORY_NAME = "render-image"


class RenderImageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo_root = Path(__file__).resolve().parent.parent

        use_prebuilt = str(self.node.try_get_context("usePrebuiltImage") or "").lower() in (
            "true",
            "1",
            "yes",
        )
        if use_prebuilt:
            image_tag = self.node.try_get_context("imageTag")
            if not image_tag or not str(image_tag).strip():
                raise ValueError(
                    "CDK context 'imageTag' is required when usePrebuiltImage=true "
                    "(full git SHA or digest of the image in ECR)."
                )
            repository = ecr.Repository.from_repository_name(
                self,
                "RenderImageRepo",
                repository_name=ECR_REPOSITORY_NAME,
            )
            image_code = lambda_.DockerImageCode.from_ecr(
                repository=repository,
                tag_or_digest=str(image_tag).strip(),
            )
        else:
            image_code = lambda_.DockerImageCode.from_image_asset(
                str(repo_root),
                file="Dockerfile.lambda",
            )

        render_fn = lambda_.DockerImageFunction(
            self,
            "RenderPdfFunction",
            code=image_code,
            memory_size=3008,
            timeout=Duration.seconds(29),
            architecture=lambda_.Architecture.X86_64,
        )

        integration = apigwv2_integrations.HttpLambdaIntegration(
            "RenderPdfIntegration",
            render_fn,
            payload_format_version=apigwv2.PayloadFormatVersion.VERSION_2_0,
        )

        http_api = apigwv2.HttpApi(
            self,
            "RenderHttpApi",
            api_name="render-image",
        )

        http_api.add_routes(
            path="/render",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )

        base_url = http_api.api_endpoint
        CfnOutput(
            self,
            "RenderApiUrl",
            value=base_url,
            description="HTTP API base URL; POST {base}/render with JSON body",
        )
