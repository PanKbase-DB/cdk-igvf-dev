from aws_cdk import Stack
from aws_cdk import Duration

from constructs import Construct

from aws_cdk.aws_iam import PolicyStatement

from aws_cdk.aws_lambda_python_alpha import PythonFunction
from aws_cdk.aws_lambda import Runtime

from aws_cdk.aws_events import Rule
from aws_cdk.aws_events import Schedule

from aws_cdk.aws_events_targets import SfnStateMachine

from aws_cdk.aws_stepfunctions import Condition
from aws_cdk.aws_stepfunctions import Choice
from aws_cdk.aws_stepfunctions import JsonPath
from aws_cdk.aws_stepfunctions import Map
from aws_cdk.aws_stepfunctions import Pass
from aws_cdk.aws_stepfunctions import Result
from aws_cdk.aws_stepfunctions import Succeed
from aws_cdk.aws_stepfunctions import StateMachine
from aws_cdk.aws_stepfunctions import TaskInput
from aws_cdk.aws_stepfunctions import Wait
from aws_cdk.aws_stepfunctions import WaitTime

from aws_cdk.aws_stepfunctions_tasks import CallAwsService
from aws_cdk.aws_stepfunctions_tasks import EventBridgePutEvents
from aws_cdk.aws_stepfunctions_tasks import EventBridgePutEventsEntry
from aws_cdk.aws_stepfunctions_tasks import LambdaInvoke


class DemoCleaner(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        succeed = Succeed(
            self,
            'Succeed',
        )

        make_success_message = Pass(
            self,
            'MakeSuccessMessage',
            parameters={
                'detailType': 'StackDeleteCompleted',
                'source': 'cdk-igvf-dev.cleaner.DemoCleaner',
                'detail': {
                    'metadata': {
                        'includes_slack_notification': True
                    },
                    'data': {
                        'slack': {
                            'text': JsonPath.format(
                                ':white_check_mark: *StackDeleteSucceeded* | {}',
                                JsonPath.string_at('$.stack_to_delete')
                            )
                        }
                    }
                }
            },
        )

        make_failure_message = Pass(
            self,
            'MakeFailureMessage',
            parameters={
                'detailType': 'StackDeleteFailed',
                'source': 'cdk-igvf-dev.cleaner.DemoCleaner.',
                'detail': {
                    'metadata': {
                        'includes_slack_notification': True
                    },
                    'data': {
                        'slack': {
                            'text': JsonPath.format(
                                ':x: *StackDeleteFailed* | {}',
                                JsonPath.string_at('$.stack_to_delete')
                            )
                        }
                    }
                }
            },
        )

        send_slack_notification = EventBridgePutEvents(
            self,
            'SendSlackNotification',
            entries=[
                EventBridgePutEventsEntry(
                    detail_type=JsonPath.string_at('$.detailType'),
                    detail=TaskInput.from_json_path_at('$.detail'),
                    source=JsonPath.string_at('$.source')
                )
            ],
            result_path=JsonPath.DISCARD,
        )

        get_stacks_to_delete_lambda = PythonFunction(
            self,
            'GetStacksToDeleteLambda',
            entry='cleaner/lambdas/cloudformation',
            runtime=Runtime.PYTHON_3_9,
            index='stacks.py',
            handler='get_stacks_to_delete',
            timeout=Duration.seconds(60),
        )

        get_stacks_to_delete_lambda.role.add_to_policy(
            PolicyStatement(
                actions=['cloudformation:DescribeStacks'],
                resources=['*'],
            )
        )

        delete_successful = Pass(
            self,
            'DeleteSuccessful'
        )

        delete_successful_routine = delete_successful.next(
            make_success_message
        ).next(
            send_slack_notification
        )

        unable_to_delete = Pass(
            self,
            'UnableToDelete'
        )

        unable_to_delete_routine = unable_to_delete.next(
            make_failure_message
        ).next(
            send_slack_notification
        )

        increment_counter_lambda = PythonFunction(
            self,
            'IncrementCounterLambda',
            entry='cleaner/lambdas/counter/',
            runtime=Runtime.PYTHON_3_9,
            index='increment.py',
            handler='increment_counter',
            timeout=Duration.seconds(60),
        )

        get_stacks_to_delete = LambdaInvoke(
            self,
            'GetStacksToDelete',
            lambda_function=get_stacks_to_delete_lambda,
            payload_response_only=True,
            result_selector={
                'stacks_to_delete.$': '$'
            }
        )

        initialize_counter = Pass(
            self,
            'InitializeCounter',
            result=Result.from_object(
                {
                    'index': 0,
                    'step': 1,
                    'count': 6,
                }
            ),
            result_path='$.iterator',
        )

        increment_counter = LambdaInvoke(
            self,
            'IncrementCounter',
            lambda_function=increment_counter_lambda,
            payload_response_only=True,
            result_path='$.iterator',
        )

        wait_ten_minutes = Wait(
            self,
            'WaitTenMinutes',
            time=WaitTime.duration(
                Duration.minutes(10)
            )
        )

        should_try_again = Choice(
            self,
            'ShouldTryAgain'
        ).when(
            Condition.boolean_equals(
                '$.iterator.continue',
                True
            ),
            increment_counter
        ).otherwise(
            unable_to_delete_routine
        )

        does_stack_exist = CallAwsService(
            self,
            'DoesStackExist',
            service='cloudformation',
            action='describeStacks',
            iam_resources=['*'],
            parameters={
                'StackName.$': '$.stack_to_delete'
            },
            result_path=JsonPath.DISCARD,
        )

        does_stack_exist.add_catch(
            delete_successful_routine,
            errors=[
                'CloudFormation.CloudFormationException'
            ],
            result_path='$.errors',
        )

        delete_stack = CallAwsService(
            self,
            'DeleteStack',
            service='cloudformation',
            action='deleteStack',
            iam_resources=['*'],
            parameters={
                'StackName.$': '$.stack_to_delete'
            },
            result_path=JsonPath.DISCARD,
        )

        delete_stack.add_catch(
            unable_to_delete_routine,
            errors=[
                'CloudFormation.CloudFormationException'
            ],
            result_path='$.errors',
        )

        clean_up_routine = increment_counter.next(
            delete_stack
        ).next(
            wait_ten_minutes
        ).next(
            does_stack_exist
        ).next(
            should_try_again
        )

        map_stacks = Map(
            self,
            'MapStacks',
            items_path='$.stacks_to_delete',
            max_concurrency=50,
            parameters={
                'stack_to_delete.$': '$$.Map.Item.Value',
                'iterator.$': '$.iterator'
            }
        )

        map_stacks.iterator(clean_up_routine)

        definition = get_stacks_to_delete.next(
            initialize_counter
        ).next(
            map_stacks
        ).next(
            succeed
        )

        state_machine = StateMachine(
            self,
            'StateMachine',
            definition=definition,
        )

        state_machine_target = SfnStateMachine(
            state_machine
        )

        Rule(
            self,
            'CleanUpDemoStacks',
            schedule=Schedule.rate(
                Duration.hours(2)
            ),
            targets=[
                state_machine_target
            ]
        )
