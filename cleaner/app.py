from aws_cdk import App
from aws_cdk import Environment

from cleaner.config import config

from cleaner.stacks.demo import DemoCleaner


ENVIRONMENT = Environment(
    account=config['account'],
    region=config['region'],
)


app = App()


DemoCleaner(
    app,
    'DemoCleaner',
    env=ENVIRONMENT,
    termination_protection=True,
)


app.synth()
