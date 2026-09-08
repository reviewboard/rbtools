"""Rich-backed console for RBTools commands.

Version Added:
    7.0
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal, Protocol

from rich.console import Console, RenderHook
from rich.logging import RichHandler
from rich.markup import escape as escape_markup
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from rbtools.ui.theme import (
    ICON_ARROW,
    ICON_ERROR,
    ICON_SUCCESS,
    ICON_WARNING,
    build_theme,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from typing import Any, TextIO, TypeAlias, TypeVar

    from rich.console import RenderableType
    from rich.live import Live
    from rich.progress import Task
    from rich.status import Status
    from rich.style import StyleType
    from typelets.json import JSONDict

    from rbtools.ui.theme import ColorOverrides

    _T = TypeVar('_T')


#: The valid color modes.
#:
#: Version Added:
#:     7.0
ColorMode: TypeAlias = Literal['always', 'auto', 'never']


_ERROR = Text(ICON_ERROR, style='rb.error')
_STEP = Text(ICON_ARROW, style='rb.step')
_SUCCESS = Text(ICON_SUCCESS, style='rb.success')
_WARNING = Text(ICON_WARNING, style='rb.warning')


def write_passthrough(
    console: Console,
    text: str,
) -> None:
    """Write text to a console verbatim.

    This emits the string exactly as-is, with no markup, styling, wrapping, or
    cropping. It is used by
    :py:class:`~rbtools.commands.base.output.OutputWrapper` to route plain
    ``stdout``/``stderr`` writes through the Rich console while keeping the
    output identical to a direct stream write.

    Version Added:
        7.0

    Args:
        console (rich.console.Console):
            The console to write to.

        text (str):
            The text to write.
    """
    console.print(text,
                  markup=False,
                  highlight=False,
                  soft_wrap=True,
                  crop=False,
                  end='')


class _SuppressRenderHook(RenderHook):
    """A Rich render hook that drops all output.

    This is pushed onto the consoles in ``--json`` mode so that any console
    output produced while the command runs is discarded, leaving only the
    JSON payload on stdout.

    Version Added:
        7.0
    """

    def process_renderables(
        self,
        renderables: list[Any],
    ) -> list[Any]:
        """Drop all renderables.

        Args:
            renderables (list):
                The renderables that were about to be rendered.

        Returns:
            list:
            An empty list.
        """
        return []


class _StepsColumn(ProgressColumn):
    """A progress column showing how far along a multi-step task is.

    If there's only a single step, this will just show the step description.
    When there is more than one step, this shows a progress bar,
    completed/total count, percentage, and a time estimate.

    Version Added:
        7.0
    """

    ######################
    # Instance variables #
    ######################

    #: The columns rendered for a multi-step task.
    _columns: list[ProgressColumn]

    def __init__(self) -> None:
        """Initialize the column."""
        super().__init__()

        self._columns = [
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
        ]

    def render(
        self,
        task: Task,
    ) -> RenderableType:
        """Render the column for a task.

        Args:
            task (rich.progress.Task):
                The task being rendered.

        Returns:
            rich.console.RenderableType:
            The rendered columns, or empty text if the task has fewer than
            two steps.
        """
        total = task.total

        if total is None or total <= 1:
            return Text('')

        grid = Table.grid(padding=(0, 1))
        grid.add_row(*(column(task) for column in self._columns))

        return grid


class _ProgressController(Protocol):
    """Protocol for a progress controller.

    Version Added:
        9.0
    """

    def advance(
        self,
        amount: int = 1,
    ) -> None:
        ...

    def update(
        self,
        message: str,
    ) -> None:
        ...


class _NullProgress:
    """A no-op progress controller.

    This is yielded by :py:meth:`RBToolsConsole.progress_bar` and used by
    :py:meth:`RBToolsConsole.spinner` when the console is disabled, so callers
    can invoke :py:meth:`advance` and :py:meth:`update` without any effect.

    Version Added:
        7.0
    """

    def advance(
        self,
        amount: int = 1,
    ) -> None:
        """Advance the progress bar.

        Args:
            amount (int, optional):
                The amount to advance by.
        """

    def update(
        self,
        message: str,
    ) -> None:
        """Update the progress message.

        Args:
            message (str):
                The new message.
        """


class _ProgressAdapter:
    """A thin adapter over a Rich :py:class:`~rich.progress.Progress` task.

    Version Added:
        7.0
    """

    def __init__(
        self,
        progress: Progress,
        task_id: Any,
        prefix: (str | None) = None,
    ) -> None:
        """Initialize the adapter.

        Args:
            progress (rich.progress.Progress):
                The progress display.

            task_id (rich.progress.TaskID):
                The ID of the task to control.

            prefix (str, optional):
                A prefix to show before any updated description.
        """
        self._progress = progress
        self._task_id = task_id
        self._prefix = prefix

    def advance(
        self,
        amount: int = 1,
    ) -> None:
        """Advance the progress bar.

        Args:
            amount (int, optional):
                The amount to advance by.
        """
        self._progress.advance(self._task_id, amount)

    def update(
        self,
        message: str,
    ) -> None:
        """Update the progress bar description.

        Args:
            message (str):
                The new description.
        """
        if self._prefix:
            message = f'{self._prefix}: {message}'

        self._progress.update(self._task_id, description=message)


class _RBToolsRichHandler(RichHandler):
    """A Rich logging handler matching RBTools' historical formatting.

    Rich's default handler shows a level column for every record. RBTools
    treats INFO messages like plain print statements, so this handler hides
    the level prefix for INFO only. DEBUG, WARNING, and higher still show the
    styled level name.

    Version Added:
        7.0
    """

    ######################
    # Instance variables #
    ######################

    #: The console that owns this handler.
    _rbtools_console: RBToolsConsole

    def __init__(
        self,
        *args,
        rbtools_console: RBToolsConsole,
        **kwargs,
    ) -> None:
        """Initialize the handler.

        Args:
            *args (tuple):
                Positional arguments to pass to
                :py:class:`rich.logging.RichHandler`.

            rbtools_console (RBToolsConsole):
                The console that owns this handler. This is used to pause any
                active spinner or progress bar while a record is written.

            **kwargs (dict):
                Keyword arguments to pass to
                :py:class:`rich.logging.RichHandler`.
        """
        super().__init__(*args, **kwargs)

        self._rbtools_console = rbtools_console

    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:
        """Write a log record.

        Log records go to the stderr console, while spinners and progress bars
        are drawn on the stdout console. Rich cannot coordinate the two, so the
        record is written with any active display paused. Otherwise the record
        would be interleaved with the animation.

        Args:
            record (logging.LogRecord):
                The log record to write.
        """
        with self._rbtools_console.pause():
            super().emit(record)

    def render(
        self,
        *,
        record: logging.LogRecord,
        traceback: Any,
        message_renderable: Any,
    ) -> Any:
        """Render a log record for display.

        The level column is hidden for INFO, so those messages appear without
        a level prefix. DEBUG, WARNING, and higher keep their level prefix.

        Args:
            record (logging.LogRecord):
                The log record to render.

            traceback (rich.traceback.Traceback):
                The traceback to render, if any.

            message_renderable (rich.console.ConsoleRenderable):
                The renderable for the log message.

        Returns:
            rich.console.ConsoleRenderable:
            The renderable to display.
        """
        self._log_render.show_level = (record.levelno != logging.INFO)

        return super().render(record=record,
                              traceback=traceback,
                              message_renderable=message_renderable)


class RBToolsConsole:
    """A Rich-backed console for RBTools commands.

    This wraps two :py:class:`rich.console.Console` instances (one for stdout
    and one for stderr) and provides RBTools-specific helpers for styled
    messages, spinners, progress bars, and tables.

    The output methods are never no-ops. When the console is enabled (writing
    to a color terminal or forced on with ``--color=always``), they emit styled
    output. When disabled (piped, redirected, or ``--color=never``), they emit
    the plain-text equivalent through the same console. This lets commands make
    a single unconditional call instead of branching on whether color is
    available.

    In ``--json`` mode, :py:meth:`suppress` is called to discard all console
    output.

    Version Added:
        7.0
    """

    ######################
    # Instance variables #
    ######################

    #: The Rich console for stderr.
    stderr_console: Console

    #: The Rich console for stdout.
    stdout_console: Console

    #: Whether console output is currently suppressed.
    _suppressed: bool

    #: The live display for the active spinner or progress bar, if any.
    _live: Live | None

    #: The active progress display, if any.
    #:
    #: Nested calls to :py:meth:`progress_bar` share this, so that a spinner
    #: stays on screen for the whole run of a command.
    _progress: Progress | None

    def __init__(
        self,
        *,
        stdout: (TextIO | None) = None,
        stderr: (TextIO | None) = None,
        color_mode: ColorMode = 'auto',
        colors: (ColorOverrides | None) = None,
    ) -> None:
        """Initialize the console.

        Args:
            stdout (io.TextIOBase, optional):
                The stream for standard output. Defaults to ``sys.stdout``.

            stderr (io.TextIOBase, optional):
                The stream for standard error. Defaults to ``sys.stderr``.

            color_mode (str, optional):
                One of ``auto`` (color when writing to a terminal), ``always``
                (always color), or ``never`` (never color).

            colors (dict, optional):
                A mapping of log level names to color names, used to build the
                theme. This comes from the ``COLOR`` configuration.
        """
        if color_mode == 'always':
            force_terminal = True
            no_color = False
        elif color_mode == 'never':
            force_terminal = False
            no_color = True
        else:
            force_terminal = None
            no_color = False

        theme = build_theme(colors)

        self.stdout_console = Console(
            file=stdout,
            theme=theme,
            highlight=False,
            force_terminal=force_terminal,
            no_color=no_color)

        self.stderr_console = Console(
            file=stderr,
            theme=theme,
            stderr=True,
            highlight=False,
            force_terminal=force_terminal,
            no_color=no_color)

        self._suppressed = False
        self._live = None
        self._progress = None

    @property
    def enabled(self) -> bool:
        """Whether styled output is active for stdout.

        Type:
            bool
        """
        return self.stdout_console.is_terminal

    @property
    def stderr_enabled(self) -> bool:
        """Whether styled output is active for stderr.

        Type:
            bool
        """
        return self.stderr_console.is_terminal

    def suppress(self) -> None:
        """Discard all subsequent console output.

        This pushes a render hook onto both consoles that drops everything. It
        is used in ``--json`` mode so only the JSON payload is written.

        The suppression on stdout is later lifted by :py:meth:`print_json`,
        which emits the JSON payload.
        """
        self.stdout_console.push_render_hook(_SuppressRenderHook())
        self.stderr_console.push_render_hook(_SuppressRenderHook())
        self._suppressed = True

    def print_json(
        self,
        data: JSONDict,
        *,
        indent: int = 4,
        sort_keys: bool = True,
    ) -> None:
        """Print structured data as JSON to stdout.

        In ``--json`` mode, output is suppressed while the command runs (see
        :py:meth:`suppress`). This lifts that suppression on the stdout console
        and renders the data through Rich's JSON renderer, so the JSON payload
        is the only thing written to stdout.

        Version Added:
            7.0

        Args:
            data (dict):
                The structured data to render as JSON.

            indent (int, optional):
                The number of spaces to indent each nesting level.

            sort_keys (bool, optional):
                Whether to sort object keys alphabetically.
        """
        if self._suppressed:
            self.stdout_console.pop_render_hook()
            self._suppressed = False

        self.stdout_console.print_json(data=data,
                                       indent=indent,
                                       sort_keys=sort_keys)

    def _emit(
        self,
        console: Console,
        message: str,
        *,
        style: (StyleType | None) = None,
        prefix: (str | None) = None,
        prefix_style: (str | None) = None,
    ) -> None:
        """Emit a message, styled or plain based on whether color is enabled.

        The message is always treated as literal text (never as Rich markup),
        so it is safe to pass arbitrary content. When disabled, the message is
        written verbatim through the console with no styling or prefix.

        Args:
            console (rich.console.Console):
                The console to write to.

            message (str):
                The literal message text.

            style (str, optional):
                A style to apply to the message when enabled.

            prefix (str, optional):
                A prefix (such as an icon) to show before the message when
                enabled. A space is added between the prefix and the message.

            prefix_style (str, optional):
                A style to apply to the prefix.
        """
        if self.enabled:
            text = Text()

            if prefix:
                text.append(f'{prefix} ', style=prefix_style or '')

            text.append(message, style=style or '')
            console.print(text)
        else:
            write_passthrough(console, message)
            write_passthrough(console, '\n')

    def print(
        self,
        *args,
        **kwargs,
    ) -> None:
        """Print a message to the stdout console.

        This will forward a message to the Rich console.

        Args:
            *args (tuple):
                Positional arguments to pass through to
                :py:meth:`rich.console.Console.print`.

            **kwargs (dict):
                Keyword arguments to pass through to
                :py:meth:`rich.console.Console.print`.
        """
        self.stdout_console.print(*args, **kwargs)

    def print_escaped(
        self,
        text: str,
        **kwargs,
    ) -> None:
        """Print a message to the stdout console without markup.

        This acts like :py:meth:`print` but will escape text before printing.

        Args:
            text (str):
                The text to print.

            **kwargs (dict):
                Additional keyword arguments to pass through to
                :py:meth:`rich.console.Console.print`.
        """
        self.print(escape_markup(text), **kwargs)

    def print_step(
        self,
        message: str,
        *,
        escape: bool = False,
    ) -> None:
        """Print a step message for a sequential operation.

        Args:
            message (str):
                The message to display.

            escape (bool, optional):
                Whether to escape the message for Rich markup.
        """
        if escape:
            message = escape_markup(message)

        self.stdout_console.print(_STEP, message)

    def print_success(
        self,
        message: str,
        *,
        escape: bool = False,
    ) -> None:
        """Print a success message.

        Args:
            message (str):
                The message to display.

            escape (bool, optional):
                Whether to escape the message for Rich markup.
        """
        if escape:
            message = escape_markup(message)

        self.stdout_console.print(_SUCCESS, message)

    def print_info(
        self,
        message: str,
        *,
        escape: bool = False,
    ) -> None:
        """Print an informational message.

        Args:
            message (str):
                The message to display.

            escape (bool, optional):
                Whether to escape the message for Rich markup.
        """
        if escape:
            message = escape_markup(message)

        self.stdout_console.print(f'[rb.info] {message}')

    def print_error(
        self,
        message: str,
        *,
        escape: bool = False,
    ) -> None:
        """Print an error message to stdout.

        This writes inline command errors to stdout, matching the historical
        behavior of commands that reported failures through ``stdout``.

        Args:
            message (str):
                The message to display.

            escape (bool, optional):
                Whether to escape the message for Rich markup.
        """
        if escape:
            message = escape_markup(message)

        self.stderr_console.print(_ERROR, message)

    def print_warning(
        self,
        message: str,
        *,
        escape: bool = False,
    ) -> None:
        """Print a warning message to stderr.

        Args:
            message (str):
                The message to display.

            escape (bool, optional):
                Whether to escape the message for Rich markup.
        """
        if escape:
            message = escape_markup(message)

        self.stdout_console.print(_WARNING, message)

    @contextmanager
    def pause(self) -> Generator[None, None, None]:
        """Temporarily hide any active spinner or progress bar.

        Rich draws spinners and progress bars by repeatedly rewriting the last
        lines of the terminal. Anything else that writes there at the same time
        ends up interleaved with the animation. That includes log records
        (which go to the stderr console) and interactive prompts (which write
        straight to the terminal, bypassing Rich).

        This erases the active display, runs the block, and then redraws the
        display where it left off. It does nothing if no display is active.

        Version Added:
            7.0

        Context:
            The active display is hidden.
        """
        live = self._live

        if live is None or not live.is_started:
            yield
            return

        # Rich only erases a live display on stop if it's transient, so
        # temporarily make it one. Otherwise a copy of the display would be
        # left behind on each pause.
        transient = live.transient
        live.transient = True
        live.stop()

        try:
            yield
        finally:
            live.transient = transient
            live.start(refresh=True)

    def spinner(
        self,
        message: str,
    ) -> Status | None:
        """Display an animated spinner while a block of work runs.

        When disabled, the message is printed as a step and a no-op controller
        is yielded.

        Args:
            message (str):
                The message to display next to the spinner.

        Returns:
            rich.status.Status:
            The status object, or ``None`` if Rich output is not enabled.
        """
        if not self.enabled:
            self.print_step(message)
            return None

        return self.stdout_console.status(message)

    @contextmanager
    def progress_bar(
        self,
        description: str,
        *,
        total: (int | None) = None,
        transient: bool = True,
    ) -> Generator[_ProgressController, None, None]:
        """Display a spinner and progress bar while a block of work runs.

        A spinner and the description are always shown. The bar, counts, and
        time estimate are only drawn when there's more than one step to
        track, since a single step would jump straight from 0% to 100%.

        These nest. When one of these blocks runs inside another, it takes
        over the display for its duration and the outer description comes
        back when it finishes. The nested description is shown after the
        outermost one, as ``"Outer: inner"``. That keeps a spinner and a
        stable label on screen for the whole run of a command, rather than
        flickering between steps.

        By default the display is erased once the outermost block finishes,
        leaving the result to be shown in its place. Pass ``transient=False``
        for work that should leave its final state on screen.

        When disabled, a no-op controller is yielded so callers can still call
        :py:meth:`advance` and :py:meth:`update`.

        Args:
            description (str):
                The label shown next to the spinner.

            total (int, optional):
                The total number of steps. If ``None`` or 1, no bar is shown.

            transient (bool, optional):
                Whether to erase the display when the work finishes. This is
                ignored when nested inside another block, which owns the
                display.

        Yields:
            object:
            A controller with ``advance(amount)`` and ``update(message)``
            methods.
        """
        if not self.enabled:
            yield _NullProgress()
            return

        progress = self._progress

        if progress is not None:
            # A display is already active. Take it over for the duration of
            # this block, hiding what it was showing, and put it back
            # afterwards. This keeps the spinner running the whole time.
            prefix = progress.tasks[0].description
            hidden = [
                task.id
                for task in progress.tasks
                if task.visible
            ]

            for task_id in hidden:
                progress.update(task_id, visible=False)

            task_id = progress.add_task(f'{prefix}: {description}',
                                        total=total)

            try:
                yield _ProgressAdapter(progress, task_id, prefix)
            finally:
                progress.remove_task(task_id)

                for task_id in hidden:
                    progress.update(task_id, visible=True)

            return

        progress = Progress(SpinnerColumn(),
                            TextColumn('[rb.step]{task.description}'),
                            _StepsColumn(),
                            console=self.stdout_console,
                            transient=transient)

        with progress:
            self._progress = progress
            self._live = progress.live

            try:
                task_id = progress.add_task(description, total=total)
                yield _ProgressAdapter(progress, task_id)
            finally:
                self._progress = None
                self._live = None

    def track(
        self,
        iterable: Iterable[_T],
        description: str,
        *,
        total: (int | None) = None,
    ) -> Iterable[_T]:
        """Wrap an iterable with a progress bar.

        When disabled, the iterable is returned unchanged.

        Args:
            iterable (iterable):
                The iterable to wrap.

            description (str):
                The label shown next to the bar.

            total (int, optional):
                The size of the iterable. Only needed when the iterable does
                not implement `:py:meth:`object.__len__`.

        Returns:
            iterable:
            The wrapped iterable, or the original when disabled.
        """
        if not self.enabled:
            return iterable

        if total is None:
            try:
                total = len(iterable)  # type: ignore[arg-type]
            except TypeError:
                pass

        return self._track(iterable, description, total=total)

    def _track(
        self,
        iterable: Iterable[_T],
        description: str,
        *,
        total: (int | None),
    ) -> Iterable[_T]:
        """Yield from an iterable, advancing a progress bar for each item.

        This backs :py:meth:`track`. It's kept separate so that ``track`` can
        return the unwrapped iterable without starting a progress bar.

        Args:
            iterable (iterable):
                The iterable to wrap.

            description (str):
                The label shown next to the bar.

            total (int):
                The size of the iterable, or ``None`` if unknown.

        Yields:
            object:
            Each item from ``iterable``.
        """
        with self.progress_bar(description, total=total) as progress:
            for item in iterable:
                yield item
                progress.advance()

    def get_rich_log_handler(
        self,
        *,
        level: int = logging.DEBUG,
        show_path: bool = False,
    ) -> _RBToolsRichHandler:
        """Return a Rich logging handler for styled log output.

        Args:
            level (int, optional):
                The minimum log level to handle.

            show_path (bool, optional):
                Whether to show the source path for each log record.

        Returns:
            _RBToolsRichHandler:
            The configured handler, writing to the stderr console.
        """
        return _RBToolsRichHandler(
            rbtools_console=self,
            console=self.stderr_console,
            level=level,
            show_time=False,
            show_path=show_path,
            rich_tracebacks=False,
            markup=False)
