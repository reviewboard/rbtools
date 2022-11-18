"""Internal support for handling deprecations in RBTools.

The version-specific objects in this module are not considered stable between
releases, and may be removed at any point. The base objects are considered
stable.
"""

import inspect
import warnings
from functools import wraps
from typing import (Any, Callable, Dict, List, Optional, Tuple, Type,
                    TypeVar, cast)


class BaseRemovedInRBToolsVersionWarning(DeprecationWarning):
    """Base class for a RBTools deprecation warning.

    All version-specific deprecation warnings inherit from this, allowing
    callers to check for Review Board deprecations without being tied to a
    specific version.
    """

    #: The version in which this warning pertains to.
    #:
    #: Version Added:
    #:     4.0
    #:
    #: Type:
    #:     str
    version: str = ''

    @classmethod
    def warn(
        cls,
        message: str,
        stacklevel: int = 2,
    ) -> None:
        """Emit the deprecation warning.

        This is a convenience function that emits a deprecation warning using
        this class, with a suitable default stack level. Callers can provide
        a useful message and a custom stack level.

        Args:
            message (unicode):
                The message to show in the deprecation warning.

            stacklevel (int, optional):
                The stack level for the warning.
        """
        warnings.warn(message, cls, stacklevel=stacklevel + 1)


class RemovedInRBTools40Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 4.0.

    Note that this class will itself be removed in RBTools 4.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '4.0'


class RemovedInRBTools50Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 5.0.

    Note that this class will itself be removed in RBTools 5.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '5.0'


class RemovedInRBTools60Warning(BaseRemovedInRBToolsVersionWarning):
    """Deprecations for features removed in RBTools 6.0.

    Note that this class will itself be removed in RBTools 6.0. If you need to
    check against RBTools deprecation warnings, please see
    :py:class:`BaseRemovedInRBToolsVersionWarning`.
    """

    version = '6.0'


_FuncT = TypeVar('_FuncT', bound=Callable[..., Any])


def deprecate_non_keyword_only_args(
    warning_cls: Type[BaseRemovedInRBToolsVersionWarning],
    message: Optional[str] = None,
) -> Callable[[_FuncT], _FuncT]:
    """Deprecate calls passing keyword-only arguments as positional arguments.

    This decorator allows code transitioning to keyword-only arguments to
    continue working when passing values as positional arguments.

    Upon the first call, it will record information about the signature of the
    function and then compare that to any future calls. If any positional
    argument values are passed to keyword-only arguments, the arguments will
    be rewritten to work correctly, and a deprecation warning will be emitted.

    Version Added:
        4.0

    Args:
        warning_cls (type):
            The specific RBTools deprecation warning class to use. This must
            be a subclass of :py:class:`BaseRemovedInRBToolsVersionWarning`.

        message (str, optional):
            An optional message to use instead of the default.

    Returns:
        callable:
        The function decorator.

    Raises:
        AssertionError:
            The function being called does not provide keyword-only arguments.
    """
    def _get_argspec_info(
        func: _FuncT,
    ) -> Tuple[List[str], int]:
        """Return cached signature and keyword-only argument index information.

        This will compute a signature for the provided function and determine
        the index of the first keyword-only argument. These values will be
        cached on the function for future lookup, so additional calls don't
        incur a penalty.

        Args:
            func (callable):
                The decorated function to inspect.

        Returns:
            tuple:
            Information on the signature:

            Tuple:
                0 (list of str):
                    The list of parameter names for the function.

                1 (int):
                    The index of the first keyword-only argument.

        Raises:
            AssertionError:
                The function being called does not provide keyword-only
                arguments.
        """
        args_cache: Dict[str, Any]
        param_names: List[str]
        first_kwonly_arg_index: int

        try:
            args_cache = getattr(func, '_rbtools_dep_kwonly_args_cache')
        except AttributeError:
            args_cache = {}
            setattr(func, '_rbtools_dep_kwonly_args_cache', args_cache)

        if args_cache:
            param_names = args_cache['param_names']
            first_kwonly_arg_index = args_cache['first_kwonly_i']
        else:
            sig = inspect.signature(func)
            first_kwonly_arg_index = -1
            param_names = []
            i = 0

            # This is guaranteed to be in the correct order.
            for param in sig.parameters.values():
                if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                    param_names.append(param.name)

                    if (param.kind == param.KEYWORD_ONLY and
                        first_kwonly_arg_index == -1):
                        first_kwonly_arg_index = i

                    i += 1

            assert first_kwonly_arg_index != -1, (
                '@deprecate_non_keyword_only_args cannot be used on '
                'functions that do not contain keyword-only arguments.')

            args_cache.update({
                'first_kwonly_i': first_kwonly_arg_index,
                'param_names': param_names,
            })

        return param_names, first_kwonly_arg_index

    def _check_call(
        func: _FuncT,
        args: Tuple,
        kwargs: Dict,
    ) -> Tuple[Tuple, Dict]:
        """Check arguments to a call and modify if necessary.

        This will check if there are any positional arguments being passed as
        keyword arguments. If found, they'll be converted to keyword arguments
        and a warning will be emitted.

        Args:
            func (callable):
                The function being decorated.

            args (tuple):
                The caller-provided positional arguments.

            kwargs (dict):
                The caller-provided keyword arguments.

        Returns:
            tuple:
            A tuple of:

            Tuple:
                0 (tuple):
                    Positional arguments to pass to ``func``.

                1 (dict):
                    Keyword arguments to pass to ``func``.
        """
        param_names, first_kwonly_arg_index = _get_argspec_info(func)
        num_args = len(args)

        if num_args <= first_kwonly_arg_index:
            # The call doesn't have to be modified.
            return args, kwargs

        # Figure out which we need to move over to keyword-only
        # arguments.
        new_args: List = []
        new_kwargs: Dict[str, Any] = kwargs.copy()
        moved_args: List[str] = []
        i = 0

        for param_name in param_names:
            if param_name not in kwargs:
                if i < first_kwonly_arg_index:
                    new_args.append(args[i])
                elif i < num_args:
                    # This must be converted to a keyword argument.
                    new_kwargs[param_name] = args[i]
                    moved_args.append(param_name)
                else:
                    # We've handled all positional arguments. We're done.
                    break

                i += 1

        new_args += args[i:]

        warning_cls.warn(
            message or (
                'Positional argument(s) %s must be passed as keyword '
                'arguments when calling %s(). This will be required in '
                'RBTools %s.'
                % (
                    ', '.join(
                        '"%s"' % _arg_name
                        for _arg_name in moved_args
                    ),
                    func.__qualname__,
                    warning_cls.version,
                )
            ),
            stacklevel=3)

        return tuple(new_args), new_kwargs

    def _dec(
        func: _FuncT,
    ) -> _FuncT:
        """Return the decorator for the function.

        Args:
            func (callable):
                The function being decorated.

        Returns:
            callable:
            The decorator for the function configured via the outer
            function's arguments.
        """
        @wraps(func)
        def _call(*args, **kwargs) -> Any:
            new_args, new_kwargs = _check_call(func, args, kwargs)

            return func(*new_args, **new_kwargs)

        return cast(_FuncT, _call)

    return _dec


RemovedInNextRBToolsVersionWarning = RemovedInRBTools50Warning
