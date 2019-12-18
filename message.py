import re
import asyncio
from typing import Callable, Iterable

from aiocqhttp.message import *

from . import NoneBot
from .log import logger
from .typing import Context_T
from .command import handle_command, SwitchException
from .natural_language import handle_natural_language
from .plugin import Plugin

_message_preprocessors = set()


class CanceledException(Exception):
    """
    Raised by message_preprocessor indicating that
    the bot should ignore the message
    """

    def __init__(self, reason):
        """
        :param reason: reason to ignore the message
        """
        self.reason = reason


def message_preprocessor(func: Callable) -> Callable:
    _message_preprocessors.add(func)
    return func


async def handle_message(bot: NoneBot, ctx: Context_T) -> None:
    _log_message(ctx)

    if not ctx['message']:
        ctx['message'].append(MessageSegment.text(''))

    raw_to_me = ctx.get('to_me', False)
    _check_at_me(bot, ctx)
    _check_calling_me_nickname(bot, ctx)
    ctx['to_me'] = raw_to_me or ctx['to_me']

    coros = []
    plugin_filtered = set()
    for processor in _message_preprocessors:
        coros.append(processor(bot, ctx))
    if coros:
        try:
            results = await asyncio.gather(*coros)
        except CanceledException:
            logger.info(f'Message {ctx["message_id"]} is ignored')
            return

        for result in results:
            if isinstance(result, Plugin):
                plugin_filtered.add(result)
            elif isinstance(result, Iterable):
                plugin_filtered |= set(
                    filter(lambda x: isinstance(x, Plugin), result))

    while True:
        try:
            handled = await handle_command(bot, ctx, plugins=plugin_filtered)
            break
        except SwitchException as e:
            # we are sure that there is no session existing now
            ctx['message'] = e.new_ctx_message
            ctx['to_me'] = True
    if handled:
        logger.info(f'Message {ctx["message_id"]} is handled as a command')
        return

    handled = await handle_natural_language(bot, ctx, plugins=plugin_filtered)
    if handled:
        logger.info(f'Message {ctx["message_id"]} is handled '
                    f'as natural language')
        return


def _check_at_me(bot: NoneBot, ctx: Context_T) -> None:
    if ctx['message_type'] == 'private':
        ctx['to_me'] = True
    else:
        # group or discuss
        ctx['to_me'] = False
        at_me_seg = MessageSegment.at(ctx['self_id'])

        # check the first segment
        first_msg_seg = ctx['message'][0]
        if first_msg_seg == at_me_seg:
            ctx['to_me'] = True
            del ctx['message'][0]

        if not ctx['to_me']:
            # check the last segment
            i = -1
            last_msg_seg = ctx['message'][i]
            if last_msg_seg.type == 'text' and \
                    not last_msg_seg.data['text'].strip() and \
                    len(ctx['message']) >= 2:
                i -= 1
                last_msg_seg = ctx['message'][i]

            if last_msg_seg == at_me_seg:
                ctx['to_me'] = True
                del ctx['message'][i:]

        if not ctx['message']:
            ctx['message'].append(MessageSegment.text(''))


def _check_calling_me_nickname(bot: NoneBot, ctx: Context_T) -> None:
    first_msg_seg = ctx['message'][0]
    if first_msg_seg.type != 'text':
        return

    first_text = first_msg_seg.data['text']

    if bot.config.NICKNAME:
        # check if the user is calling me with my nickname
        if isinstance(bot.config.NICKNAME, str) or \
                not isinstance(bot.config.NICKNAME, Iterable):
            nicknames = (bot.config.NICKNAME,)
        else:
            nicknames = filter(lambda n: n, bot.config.NICKNAME)
        nickname_regex = '|'.join(nicknames)
        m = re.search(rf'^({nickname_regex})([\s,，]*|$)',
                      first_text, re.IGNORECASE)
        if m:
            nickname = m.group(1)
            logger.debug(f'User is calling me {nickname}')
            ctx['to_me'] = True
            first_msg_seg.data['text'] = first_text[m.end():]


def _log_message(ctx: Context_T) -> None:
    msg_from = str(ctx['user_id'])
    if ctx['message_type'] == 'group':
        msg_from += f'@[群:{ctx["group_id"]}]'
    elif ctx['message_type'] == 'discuss':
        msg_from += f'@[讨论组:{ctx["discuss_id"]}]'
    logger.info(f'Self: {ctx["self_id"]}, '
                f'Message {ctx["message_id"]} from {msg_from}: '
                f'{ctx["message"]}')
