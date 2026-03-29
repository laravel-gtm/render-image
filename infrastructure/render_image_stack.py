"""CDK stack: PDF render Lambda (container) behind HTTP API Gateway."""

from pathlib import Path

from aws_cdk import (
    CfnOutput,
    Duration,
    Stack,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_certificatemanager as acm,
    aws_ecr as ecr,
    aws_lambda as lambda_,
    aws_route53 as route53,
    aws_route53_targets as route53_targets,
)
from constructs import Construct


class RenderImageStack(Stack):  # pylint: disable=too-few-public-methods
    """Lambda container function and HTTP API with POST /render, GET /up, and GET /openapi.json."""

    def _docker_image_code(
        self, repo_root: Path
    ) -> tuple[lambda_.DockerImageCode, str]:
        image_name = self.node.try_get_context("imageName") or "render-image"
        use_prebuilt = str(
            self.node.try_get_context("usePrebuiltImage") or ""
        ).lower() in (
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
                repository_name=image_name,
            )
            code = lambda_.DockerImageCode.from_ecr(
                repository=repository,
                tag_or_digest=str(image_tag).strip(),
            )
        else:
            code = lambda_.DockerImageCode.from_image_asset(
                str(repo_root),
                file="Dockerfile.lambda",
            )
        return code, image_name

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo_root = Path(__file__).resolve().parent.parent

        memory_mb = int(self.node.try_get_context("lambdaMemoryMb") or 3008)
        timeout_seconds = int(self.node.try_get_context("lambdaTimeoutSeconds") or 29)

        image_code, image_name = self._docker_image_code(repo_root)

        render_fn = lambda_.DockerImageFunction(
            self,
            "RenderPdfFunction",
            code=image_code,
            memory_size=memory_mb,
            timeout=Duration.seconds(timeout_seconds),
            architecture=lambda_.Architecture.X86_64,
        )

        # DockerImageFunction implements IFunction; ty does not infer it here.
        integration = apigwv2_integrations.HttpLambdaIntegration(
            "RenderPdfIntegration",
            render_fn,  # ty: ignore[invalid-argument-type]  # pyright: ignore[reportArgumentType]
            payload_format_version=apigwv2.PayloadFormatVersion.VERSION_2_0,
        )

        http_api = apigwv2.HttpApi(
            self,
            "RenderHttpApi",
            api_name=image_name,
        )

        http_api.add_routes(
            path="/render",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )

        http_api.add_routes(
            path="/up",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )

        http_api.add_routes(
            path="/openapi.json",
            methods=[apigwv2.HttpMethod.GET],
            integration=integration,
        )

        base_url = http_api.api_endpoint
        CfnOutput(
            self,
            "RenderApiUrl",
            value=base_url,
            description="HTTP API base URL; POST /render, GET /up, GET /openapi.json",
        )

        self._configure_custom_domain(http_api)

    def _configure_custom_domain(self, http_api: apigwv2.HttpApi) -> None:
        """Optionally attach a custom domain backed by Route 53 + ACM."""
        zone_name = self.node.try_get_context("hostedZoneName")
        cert_arn = self.node.try_get_context("certificateArn")
        if not zone_name or not cert_arn:
            return

        fqdn = f"api-{self.region}.{zone_name}"

        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone", domain_name=zone_name, private_zone=True
        )

        certificate = acm.Certificate.from_certificate_arn(
            self, "Certificate", cert_arn
        )

        domain_name = apigwv2.DomainName(
            self, "CustomDomain", domain_name=fqdn, certificate=certificate
        )

        apigwv2.ApiMapping(self, "ApiMapping", api=http_api, domain_name=domain_name)

        route53.ARecord(
            self,
            "CustomDomainARecord",
            zone=hosted_zone,
            record_name=fqdn,
            target=route53.RecordTarget.from_alias(
                route53_targets.ApiGatewayv2DomainProperties(  # ty: ignore[invalid-argument-type]
                    domain_name.regional_domain_name,
                    domain_name.regional_hosted_zone_id,
                )
            ),
        )

        CfnOutput(self, "CustomDomainUrl", value=f"https://{fqdn}")
