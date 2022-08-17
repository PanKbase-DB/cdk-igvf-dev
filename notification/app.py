#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_igvf_dev.notification_stack import NotificationStack
from cdk_igvf_dev.config import config


ENVIRONMENT = cdk.Environment(
    account=config['account'],
    region=config['region'],
)

app = cdk.App()

NotificationStack(
    app,
    'NotificationStack',
    env=ENVIRONMENT,
    termination_protection=True,
)

app.synth()
