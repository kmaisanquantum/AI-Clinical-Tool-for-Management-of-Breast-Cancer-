from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("", RedirectView.as_view(url="/api/v1/docs/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/accounts/", include("apps.accounts.urls")),
    path("api/v1/registry/", include("apps.registry.urls")),
    path("api/v1/clinical/", include("apps.clinical.urls")),
    path("api/v1/investigations/", include("apps.investigations.urls")),
    path("api/v1/decision-support/", include("apps.decision_support.urls")),
    path("api/v1/audit/", include("apps.audit.urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
