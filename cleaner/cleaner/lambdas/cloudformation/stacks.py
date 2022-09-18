import boto3
import logging

from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo


logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


OKAY_STATUSES = [
    'CREATE_FAILED',
    'CREATE_COMPLETE',
    'ROLLBACK_FAILED',
    'ROLLBACK_COMPLETE',
    'DELETE_FAILED',
    'UPDATE_COMPLETE',
    'UPDATE_FAILED',
    'UPDATE_ROLLBACK_FAILED',
    'UPDATE_ROLLBACK_COMPLETE',
    'IMPORT_COMPLETE',
    'IMPORT_ROLLBACK_FAILED',
    'IMPORT_ROLLBACK_COMPLETE'
]


TIME_TO_LIVE_HOURS = 'time-to-live-hours'
TURN_OFF_ON_FRIDAY_NIGHT = 'turn-off-on-friday-night'

SECONDS_IN_AN_HOUR = 3600
SATURDAY_WEEKDAY_NUMBER = 5


def get_cloudformation_client():
    return boto3.client('cloudformation')


def get_describe_stacks_paginator(client):
    return client.get_paginator('describe_stacks')


def get_all_stacks(paginator):
    return [
        stack
        for result in paginator.paginate()
        for stack in result['Stacks']
    ]


def filter_stacks_by_statuses(stacks):
    return [
        stack
        for stack in stacks
        if stack['StackStatus'] in OKAY_STATUSES
    ]


def get_tag_by_key(stack, key):
    for tag in stack['Tags']:
        if tag['Key'] == key:
            return tag
    return None


def get_time_to_live_hours_tag_or_none(stack):
    return get_tag_by_key(stack, TIME_TO_LIVE_HOURS)


def stack_has_time_to_live_hours_tag(stack):
    return get_time_to_live_hours_tag_or_none(stack) is not None


def filter_stacks_with_time_to_live_hours_tag(stacks):
    return [
        stack
        for stack in stacks
        if stack_has_time_to_live_hours_tag(stack)
    ]


def get_turn_off_on_friday_night_tag_or_none(stack):
    return get_tag_by_key(stack, TURN_OFF_ON_FRIDAY_NIGHT)


def stack_has_turn_off_on_friday_night_tag(stack):
    return get_turn_off_on_friday_night_tag_or_none(stack) is not None


def filter_stacks_with_turn_off_on_friday_night_tag(stacks):
    return [
        stack
        for stack in stacks
        if stack_has_turn_off_on_friday_night_tag(stack)
    ]


def get_stack_name(stack):
    return stack['StackName']


def get_creation_time(stack):
    return stack['CreationTime']


def try_parse_time_to_live_hours_tag(tag):
    try:
        return int(tag['Value'])
    except ValueError:
        logger.warning('Tag value not int')


def get_current_utc_time():
    return datetime.now(timezone.utc)


def get_current_pacific_time():
    return datetime.now(ZoneInfo('US/Pacific'))


def is_saturday(now):
    return now.weekday() == SATURDAY_WEEKDAY_NUMBER


def is_before_seven_in_the_morning(now):
    return now.hour < 7


def is_it_friday_night_in_LA():
    now_pacific = get_current_pacific_time()
    return is_saturday(now_pacific) and is_before_seven_in_the_morning(now_pacific)


def log_time_info(now, then, time_to_live_hours, hours_alive):
    logger.info(f'creation time: {then}')
    logger.info(f'now: {now}')
    logger.info(f'hours to live: {time_to_live_hours}')
    logger.info(f'hours alive: {hours_alive}')


def time_to_live_hours_exceeded(creation_time, time_to_live_hours):
    now = get_current_utc_time()
    then = creation_time
    delta = now - then
    hours_alive = int(delta.total_seconds() // SECONDS_IN_AN_HOUR)
    log_time_info(now, then, time_to_live_hours, hours_alive)
    return hours_alive >= time_to_live_hours


def stack_is_alive_longer_than_time_to_live_hours(stack):
    logger.info(
        f'Checking if {get_stack_name(stack)} is alive longer than time to live hours'
    )
    creation_time = get_creation_time(
        stack
    )
    time_to_live_hours_tag = get_time_to_live_hours_tag_or_none(
        stack
    )
    time_to_live_hours = try_parse_time_to_live_hours_tag(
        time_to_live_hours_tag
    )
    if time_to_live_hours is not None:
        return time_to_live_hours_exceeded(
            creation_time,
            time_to_live_hours
        )
    return False


def filter_stacks_living_longer_than_time_to_live_hours(stacks):
    return [
        stack
        for stack in stacks
        if stack_is_alive_longer_than_time_to_live_hours(stack)
    ]


def stack_has_turn_off_on_friday_night_yes_tag(stack):
    tag = get_turn_off_on_friday_night_tag_or_none(stack)
    if tag is not None:
        return tag['Value'] == 'yes'
    return False


def filter_stacks_by_turn_off_on_friday_night_is_yes(stacks):
    return [
        stack
        for stack in stacks
        if stack_has_turn_off_on_friday_night_yes_tag(stack)
    ]


def get_stacks_to_delete_because_of_time_to_live_hours_tag():
    client = get_cloudformation_client()
    paginator = get_describe_stacks_paginator(client)
    stacks = get_all_stacks(paginator)
    stacks = filter_stacks_by_statuses(stacks)
    stacks = filter_stacks_with_time_to_live_hours_tag(stacks)
    stacks = filter_stacks_living_longer_than_time_to_live_hours(stacks)
    return stacks


def get_stacks_to_delete_because_it_is_friday_night():
    client = get_cloudformation_client()
    paginator = get_describe_stacks_paginator(client)
    stacks = get_all_stacks(paginator)
    stacks = filter_stacks_by_statuses(stacks)
    stacks = filter_stacks_with_turn_off_on_friday_night_tag(stacks)
    stacks = filter_stacks_by_turn_off_on_friday_night_is_yes(stacks)
    return stacks


def maybe_get_stacks_to_delete_because_it_is_friday_night():
    if is_it_friday_night_in_LA():
        logger.info('It is Friday night, getting stacks to delete!')
        return get_stacks_to_delete_because_it_is_friday_night()
    else:
        return []


def get_stack_names_from_stacks(stacks):
    return [
        get_stack_name(stack)
        for stack in stacks
    ]


def get_stacks_to_delete(event, context):
    list_of_lists_of_stacks_to_delete = [
        get_stacks_to_delete_because_of_time_to_live_hours_tag(),
        maybe_get_stacks_to_delete_because_it_is_friday_night(),
        # Extend with other routines here.
    ]
    stacks_to_delete = [
        stack
        for stack_list in list_of_lists_of_stacks_to_delete
        for stack in stack_list
    ]
    stack_names_to_delete = get_stack_names_from_stacks(
        stacks_to_delete
    )
    unique_stack_names_to_delete = set()
    unique_stack_names_to_delete.update(
        stack_names_to_delete
    )
    logger.info(f'Stacks to delete: {unique_stack_names_to_delete}')
    return list(unique_stack_names_to_delete)
