#!/usr/bin/env python3

import os

import aws_cdk as cdk

from render_image_stack import RenderImageStack

app = cdk.App()
stack_name = app.node.try_get_context("stackName") or "RenderImageStack"

# HostedZone.from_lookup() requires a concrete env (account + region).
# When no custom domain is configured, env stays unset (environment-agnostic).
kwargs: dict = {}
if app.node.try_get_context("hostedZoneName"):
    kwargs["env"] = cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ["CDK_DEFAULT_REGION"],
    )

RenderImageStack(app, stack_name, **kwargs)
app.synth()
