from allauth.account.models import EmailAddress
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class PortalAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        # Internally provisioned employees retain username/password login. Public
        # password accounts must satisfy the same email gate as allauth login.
        if getattr(user, "citizenprofile", None) and not EmailAddress.objects.filter(user=user, verified=True, email__iexact=user.email).exists():
            raise ValidationError(self.error_messages["invalid_login"], code="invalid_login", params={"username": self.username_field.verbose_name})
