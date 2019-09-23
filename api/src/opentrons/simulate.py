""" opentrons.simulate: functions and entrypoints for simulating protocols

This module has functions that provide a console entrypoint for simulating
a protocol from the command line.
"""

import argparse
import sys
import logging
import queue
from typing import Any, List, Mapping, TextIO

import opentrons
import opentrons.commands
import opentrons.broker
from opentrons.config import feature_flags
from opentrons.protocols import parse
from opentrons.protocols.types import JsonProtocol


class AccumulatingHandler(logging.Handler):
    def __init__(self, level, command_queue):
        """ Create the handler

        :param level: The logging level to capture
        :param command_queue: The queue.Queue to use for messages
        """
        self._command_queue = command_queue
        super().__init__(level)

    def emit(self, record):
        self._command_queue.put(record)


class CommandScraper:
    """ An object that handles scraping the broker for commands

    This should be instantiated with the logger to integrate
    messages from (e.g. ``logging.getLogger('opentrons')``), the
    level to scrape, and the opentrons broker object to subscribe to.

    The :py:attr:`commands` property contains the list of commands
    and log messages integrated together. Each element of the list is
    a dict following the pattern in the docs of :py:meth:`simulate`.
    """
    def __init__(self,
                 logger: logging.Logger,
                 level: str,
                 broker: opentrons.broker.Broker) -> None:
        """ Build the scraper.

        :param logger: The :py:class:`logging.logger` to scrape
        :param level: The log level to scrape
        :param broker: Which broker to subscribe to
        """
        self._logger = logger
        self._broker = broker
        self._queue = queue.Queue()  # type: ignore
        if level != 'none':
            level = getattr(logging, level.upper(), logging.WARNING)
            self._logger.setLevel(level)
            logger.addHandler(
                AccumulatingHandler(
                    level,
                    self._queue))
        self._depth = 0
        self._commands: List[Mapping[str, Mapping[str, Any]]] = []
        self._unsub = self._broker.subscribe(
            opentrons.commands.command_types.COMMAND,
            self._command_callback)

    @property
    def commands(self) -> List[Mapping[str, Mapping[str, Any]]]:
        """ The list of commands. See :py:meth:`simulate` """
        return self._commands

    def __del__(self):
        if hasattr(self, '_handler'):
            self._logger.removeHandler(self._handler)
        if hasattr(self, '_unsub'):
            self._unsub()

    def _command_callback(self, message):
        """ The callback subscribed to the broker """
        payload = message['payload']
        if message['$'] == 'before':
            self._commands.append({'level': self._depth,
                                   'payload': payload,
                                   'logs': []})
            self._depth += 1
        else:
            while not self._queue.empty():
                self._commands[-1]['logs'].append(self._queue.get())
            self._depth = max(self._depth-1, 0)


def simulate(protocol_file: TextIO,
             propagate_logs=False,
             log_level='warning') -> List[Mapping[str, Any]]:
    """
    Simulate the protocol itself.

    This is a one-stop function to simulate a protocol, whether python or json,
    no matter the api version, from external (i.e. not bound up in other
    internal server infrastructure) sources.

    To simulate an opentrons protocol from other places, pass in a file like
    object as protocol_file; this function either returns (if the simulation
    has no problems) or raises an exception.

    To call from the command line use either the autogenerated entrypoint
    ``opentrons_simulate`` (``opentrons_simulate.exe``, on windows) or
    ``python -m opentrons.simulate``.

    The return value is the run log, a list of dicts that represent the
    commands executed by the robot. Each dict has the following keys:

        - ``level``: The depth at which this command is nested - if this an
                     aspirate inside a mix inside a transfer, for instance,
                     it would be 3.
        - ``payload``: The command, its arguments, and how to format its text.
                       For more specific details see
                       :py:mod:`opentrons.commands`. To format a message from
                       a payload do ``payload['text'].format(**payload)``.
        - ``logs``: Any log messages that occurred during execution of this
                    command, as a logging.LogRecord

    :param file-like protocol_file: The protocol file to simulate.
    :param propagate_logs: Whether this function should allow logs from the
                           Opentrons stack to propagate up to the root handler.
                           This can be useful if you're integrating this
                           function in a larger application, but most logs that
                           occur during protocol simulation are best associated
                           with the actions in the protocol that cause them.
                           Default: ``False``
    :type propagate_logs: bool
    :param log_level: The level of logs to capture in the runlog. Default:
                      ``'warning'``
    :type log_level: 'debug', 'info', 'warning', or 'error'
    :returns List[Dict[str, Dict[str, Any]]]: A run log for user output.
    """
    stack_logger = logging.getLogger('opentrons')
    stack_logger.propagate = propagate_logs

    contents = protocol_file.read()
    protocol = parse.parse(contents, protocol_file.name)

    if feature_flags.use_protocol_api_v2():
        import opentrons.protocol_api.execute
        context = opentrons.protocol_api.contexts.ProtocolContext()
        context.home()
        scraper = CommandScraper(stack_logger, log_level, context.broker)
        opentrons.protocol_api.execute.run_protocol(protocol,
                                                    simulate=True,
                                                    context=context)
    else:
        import opentrons.legacy_api.protocols
        opentrons.robot.disconnect()
        scraper = CommandScraper(stack_logger, log_level,
                                 opentrons.robot.broker)
        if isinstance(protocol, JsonProtocol):
            opentrons.legacy_api.protocols.execute_protocol(protocol)
        else:
            exec(protocol.contents, {})
    return scraper.commands


def format_runlog(runlog: List[Mapping[str, Any]]) -> str:
    """
    Format a run log (return value of :py:meth:`simulate``) into a
    human-readable string

    :param runlog: The output of a call to :py:func:`simulate`
    """
    to_ret = []
    for command in runlog:
        to_ret.append(
            '\t' * command['level']
            + command['payload'].get('text', '').format(**command['payload']))
        if command['logs']:
            to_ret.append('\t' * command['level'] + 'Logs from this command:')
            to_ret.extend(
                ['\t' * command['level']
                 + f'{l.levelname} ({l.module}): {l.msg}' % l.args
                 for l in command['logs']])
    return '\n'.join(to_ret)


def get_arguments(
        parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """ Get the argument parser for this module

    Useful if you want to use this module as a component of another CLI program
    and want to add its arguments.

    :param parser: A parser to add arguments to. If not specified, one will be
                   created.
    :returns argparse.ArgumentParser: The parser with arguments added.
    """
    parser.add_argument(
        '-l', '--log-level',
        choices=['debug', 'info', 'warning', 'error', 'none'],
        default='warning',
        help='Specify the level filter for logs to show on the command line. '
        'Log levels below warning can be chatty. If "none", do not show logs')
    parser.add_argument(
        'protocol', metavar='PROTOCOL',
        type=argparse.FileType('rb'),
        help='The protocol file to simulate. If you pass \'-\', you can pipe '
        'the protocol via stdin; this could be useful if you want to use this '
        'utility as part of an automated workflow.')
    return parser


# Note - this script is also set up as a setuptools entrypoint and thus does
# an absolute minimum of work since setuptools does something odd generating
# the scripts
def main() -> int:
    """ Run the simulation """
    parser = argparse.ArgumentParser(prog='opentrons_simulate',
                                     description='Simulate an OT-2 protocol')
    parser = get_arguments(parser)
    # don't want to add this in get_arguments because if somebody upstream is
    # using that parser they probably want their own version
    parser.add_argument(
        '-v', '--version', action='version',
        version=f'%(prog)s {opentrons.__version__}',
        help='Print the opentrons package version and exit')
    parser.add_argument(
        '-o', '--output', action='store',
        help='What to output during simulations',
        choices=['runlog', 'nothing'],
        default='runlog')

    args = parser.parse_args()

    runlog = simulate(args.protocol, log_level=args.log_level)
    if args.output == 'runlog':
        print(format_runlog(runlog))
    return 0


if __name__ == '__main__':
    sys.exit(main())
