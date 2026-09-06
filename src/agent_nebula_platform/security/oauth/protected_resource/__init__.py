"""Protected-resource runtime APIs."""

from .factory import ProtectedResourceRuntime, ProtectedResourceRuntimeFactory
from .models import AuthorizedRequestContext, ProtectedResourceRequest
from .policy import ExactScopeAuthorizationPolicy
from .ports import ProtectedResourceAuthorizationPolicy
from .service import ProtectedResourceService

__all__ = [
    "AuthorizedRequestContext",
    "ExactScopeAuthorizationPolicy",
    "ProtectedResourceAuthorizationPolicy",
    "ProtectedResourceRequest",
    "ProtectedResourceRuntime",
    "ProtectedResourceRuntimeFactory",
    "ProtectedResourceService",
]
