from rest_framework.routers import DefaultRouter

from .views import RolePermissionViewSet, RoleViewSet, UserRoleViewSet, UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"user-roles", UserRoleViewSet, basename="user-role")
router.register(r"role-permissions", RolePermissionViewSet, basename="role-permission")

urlpatterns = router.urls
