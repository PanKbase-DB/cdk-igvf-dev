import pytest

import json

from aws_cdk import Environment


ENVIRONMENT = Environment(
    account='testing',
    region='testing'
)


def test_match_with_snapshot(snapshot):
    from aws_cdk import App
    from cleaner.stacks.demo import DemoCleaner
    from aws_cdk.assertions import Template
    app = App()
    stack = DemoCleaner(
        app,
        'DemoCleaner',
        env=ENVIRONMENT
    )
    template = Template.from_stack(stack)
    snapshot.assert_match(
        json.dumps(
            template.to_json(),
            indent=4,
            sort_keys=True
        ),
        'demo_cleaner_template.json'
    )
