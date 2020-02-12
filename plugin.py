import os
import re
import importlib
from types import ModuleType
from typing import Any, Set, Optional

from .log import logger
from .command import CommandFunc
from .natural_language import NLProcessor


class Plugin:
    __slots__ = ('module', 'name', 'description', 'usage',
                 'commands', 'nlprocessors', 'subplugins')

    def __init__(self, module: Any,
                 commands: Set[CommandFunc],
                 nlprocessors: Set[NLProcessor],
                 name: Optional[str] = None,
                 description: Optional[str] = None,
                 usage: Optional[Any] = None,
                 subplugins: Set["Plugin"] = set()):
        self.module = module
        self.name = name
        self.description = description
        self.usage = usage
        self.commands = commands
        self.nlprocessors = nlprocessors
        self.subplugins = subplugins

    def __str__(self):
        return f"Plugin name: {self.name}, usage: {self.usage}"

    def __repr__(self):
        return f"Plugin({self.module}, name={self.name})"


_plugins: Set[Plugin] = set()


def get_cmd_nlp_subplugins(_module, depth=True):
    commands = set()
    nlprocessors = set()
    subplugins = set()
    for attr in dir(_module):
        func = getattr(_module, attr)
        if depth and isinstance(func, ModuleType):
            cmd, nlp, sup = get_cmd_nlp_subplugins(func, False)
            commands |= cmd
            nlprocessors |= nlp
            subplugins |= sup
        elif isinstance(func, CommandFunc):
            commands.add(func.cmd.name)
        elif isinstance(func, NLProcessor):
            nlprocessors.add(func)
        elif isinstance(func, set):
            subplugins |= set(filter(lambda x: isinstance(x, Plugin), func))
    return commands, nlprocessors, subplugins


def load_plugin(module_name: str) -> bool:
    """
    Load a module as a plugin.

    :param module_name: name of module to import
    :return: successful or not
    """
    try:
        module = importlib.import_module(module_name)
        name = getattr(module, '__plugin_name__', None)
        description = getattr(module, '__plugin_description__', None)
        usage = getattr(module, '__plugin_usage__', None)
        commands, nlprocessors, subplugins = get_cmd_nlp_subplugins(module)
        _plugins.add(Plugin(module=module,
                            commands=commands,
                            nlprocessors=nlprocessors,
                            name=name,
                            description=description,
                            usage=usage,
                            subplugins=subplugins))
        logger.debug(f"Succeeded to load commands {commands},"
                     f" nlprocessors {nlprocessors}"
                     f" subplugins {subplugins}")
        logger.info(f'Succeeded to import "{module_name}"')
        return True
    except Exception as e:
        logger.error(f'Failed to import "{module_name}", error: {e}')
        logger.exception(e)
        return False


def load_plugins(plugin_dir: str, module_prefix: str) -> int:
    """
    Find all non-hidden modules or packages in a given directory,
    and import them with the given module prefix.

    :param plugin_dir: plugin directory to search
    :param module_prefix: module prefix used while importing
    :return: number of plugins successfully loaded
    """
    count = 0
    for name in os.listdir(plugin_dir):
        path = os.path.join(plugin_dir, name)
        if os.path.isfile(path) and \
                (name.startswith('_') or not name.endswith('.py')):
            continue
        if os.path.isdir(path) and \
                (name.startswith('_') or not os.path.exists(
                    os.path.join(path, '__init__.py'))):
            continue

        m = re.match(r'([_A-Z0-9a-z]+)(.py)?', name)
        if not m:
            continue

        if load_plugin(f'{module_prefix}.{m.group(1)}'):
            count += 1
    return count


def load_builtin_plugins() -> int:
    """
    Load built-in plugins distributed along with "nonebot" package.
    """
    plugin_dir = os.path.join(os.path.dirname(__file__), 'plugins')
    return load_plugins(plugin_dir, 'nonebot.plugins')


def get_loaded_plugins() -> Set[Plugin]:
    """
    Get all plugins loaded.

    :return: a set of Plugin objects
    """
    return _plugins
