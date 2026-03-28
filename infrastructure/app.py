#!/usr/bin/env python3

import aws_cdk as cdk

from render_image_stack import RenderImageStack

app = cdk.App()
RenderImageStack(app, "RenderImageStack")
app.synth()
