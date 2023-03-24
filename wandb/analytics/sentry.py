__all__ = ("Sentry",)


import functools
import os
import sys
from types import TracebackType
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, Type, Union
from urllib.parse import quote

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

import sentry_sdk  # type: ignore
import sentry_sdk.utils  # type: ignore

import wandb
import wandb.env
import wandb.util

if TYPE_CHECKING:
    import wandb.sdk.internal.settings_static

SENTRY_DEFAULT_DSN = (
    "https://2592b1968ea94cca9b5ef5e348e094a7@o151352.ingest.sentry.io/4504800232407040"
)

SessionStatus = Literal["ok", "exited", "crashed", "abnormal"]


def _noop_if_disabled(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(self: Type["Sentry"], *args: Any, **kwargs: Any) -> Any:
        if self._disabled:
            return None
        return func(self, *args, **kwargs)

    return wrapper


class Sentry:
    _disabled: bool

    def __init__(self) -> None:
        self._disabled = not wandb.env.error_reporting_enabled()
        self._sent_messages: set = set()

        self.dsn = os.environ.get(wandb.env.SENTRY_DSN, SENTRY_DEFAULT_DSN)

        self.client: Optional["sentry_sdk.client.Client"] = None
        self.hub: Optional["sentry_sdk.hub.Hub"] = None

    @property
    def environment(self) -> str:
        # check if we're in a git repo
        is_git = os.path.exists(
            os.path.join(os.path.dirname(__file__), "../../", ".git")
        )
        # these match the environments for gorilla
        return "development" if is_git else "production"

    @_noop_if_disabled
    def setup(self) -> None:
        self.client = sentry_sdk.Client(
            dsn=self.dsn,
            default_integrations=False,
            environment=self.environment,
            release=wandb.__version__,
        )
        self.hub = sentry_sdk.Hub(self.client)

    @_noop_if_disabled
    def message(self, message: str, repeat: bool = True) -> None:
        if not repeat and message in self._sent_messages:
            return
        self._sent_messages.add(message)
        self.hub.capture_message(message)  # type: ignore

    @_noop_if_disabled
    def exception(
        self,
        exc: Union[
            str,
            BaseException,
            Tuple[
                Optional[Type[BaseException]],
                Optional[BaseException],
                Optional[TracebackType],
            ],
            None,
        ],
        handled: bool = False,
        status: Optional["SessionStatus"] = None,
    ) -> None:
        error = Exception(exc) if isinstance(exc, str) else exc
        # based on self.hub.capture_exception(_exc)
        if error is not None:
            exc_info = sentry_sdk.utils.exc_info_from_error(error)
        else:
            exc_info = sys.exc_info()

        event, hint = sentry_sdk.utils.event_from_exception(
            exc_info,
            client_options=self.hub.client.options,  # type: ignore
            mechanism={"type": "generic", "handled": handled},
        )
        try:
            self.hub.capture_event(event, hint=hint)  # type: ignore
        except Exception:
            self.hub._capture_internal_exception(sys.exc_info())  # type: ignore

        # if the status is not explicitly set, we'll set it to "crashed" if the exception
        # was unhandled, or "errored" if it was handled
        status = status or ("crashed" if not handled else "errored")  # type: ignore
        self.mark_session(status=status)

        client, _ = self.hub._stack[-1]
        client.flush()

        return None

    def reraise(self, exc: Any) -> None:
        """Re-raise an exception after logging it to Sentry.

        Use this for top-level exceptions when you want the user to see the traceback.

        Must be called from within an exception handler.
        """
        self.exception(exc)
        # this will messily add this "reraise" function to the stack trace,
        # but hopefully it's not too bad
        raise exc.with_traceback(sys.exc_info()[2])

    @_noop_if_disabled
    def start_session(self) -> None:
        """Track session to get metrics about error-free rate."""
        assert self.hub is not None
        _, scope = self.hub._stack[-1]
        session = scope._session

        if session is None:
            self.hub.start_session()

    @_noop_if_disabled
    def end_session(self) -> None:
        """End the current session."""
        assert self.hub is not None
        client, scope = self.hub._stack[-1]
        session = scope._session

        if session is not None and client is not None:
            self.hub.end_session()
            client.flush()

    @_noop_if_disabled
    def mark_session(self, status: Optional["SessionStatus"] = None) -> None:
        """Update the status of the current session."""
        assert self.hub is not None
        _, scope = self.hub._stack[-1]
        session = scope._session

        if session is not None:
            session.update(status=status)

    @_noop_if_disabled
    def configure_scope(
        self,
        settings: Optional[
            Union[
                "wandb.sdk.wandb_settings.Settings",
                "wandb.sdk.internal.settings_static.SettingsStatic",
            ]
        ] = None,
        process_context: Optional[str] = None,
    ) -> None:
        """Set the Sentry scope for the current thread.

        This function should be called at the beginning of every thread that
        will send events to Sentry. It sets the tags that will be applied to
        all events sent from this thread.
        """
        assert self.hub is not None
        settings_tags = (
            "entity",
            "project",
            "run_id",
            "run_url",
            "sweep_url",
            "sweep_id",
            "deployment",
            "_disable_service",
            "launch",
        )

        with self.hub.configure_scope() as scope:
            scope.set_tag("platform", wandb.util.get_platform_name())

            # set context
            if process_context:
                scope.set_tag("process_context", process_context)

            # apply settings tags
            if settings is None:
                return None

            for tag in settings_tags:
                val = settings[tag]
                if val not in (None, ""):
                    scope.set_tag(tag, val)

            # todo: update once #4982 is merged
            python_runtime = (
                "colab"
                if settings["_colab"]
                else ("jupyter" if settings["_jupyter"] else "python")
            )
            scope.set_tag("python_runtime", python_runtime)

            # Hack for constructing run_url and sweep_url given run_id and sweep_id
            required = ("entity", "project", "base_url")
            params = {key: settings[key] for key in required}
            if all(params.values()):
                # here we're guaranteed that entity, project, base_url all have valid values
                app_url = wandb.util.app_url(params["base_url"])
                ent, proj = (quote(params[k]) for k in ("entity", "project"))

                # TODO: the settings object will be updated to contain run_url and sweep_url
                # This is done by passing a settings_map in the run_start protocol buffer message
                for word in ("run", "sweep"):
                    _url, _id = f"{word}_url", f"{word}_id"
                    if not settings[_url] and settings[_id]:
                        scope.set_tag(
                            _url, f"{app_url}/{ent}/{proj}/{word}s/{settings[_id]}"
                        )

            if hasattr(settings, "email"):
                scope.user = {"email": settings.email}  # noqa

        self.start_session()
