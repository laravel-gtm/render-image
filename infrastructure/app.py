#!/usr/bin/env python3

import aws_cdk as cdk

from render_image_stack import RenderImageStack

app = cdk.App()
stack_name = app.node.try_get_context("stackName") or "RenderImageStack"
RenderImageStack(app, stack_name)
app.synth()
