from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views     # for auths for logins and logouts
from django.urls import path, include, reverse_lazy
from users.views import (
    register,
    employeeRegister,
    user_search_view,
    CustomPasswordResetView
)

from django.contrib import messages

class LoginView(auth_views.LoginView):
    def form_valid(self, form):
        messages.success(self.request, 'You have successfully logged in.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username or password.')
        return super().form_invalid(form)
    
    # removed line due to redundancy, the default success URL is already set to 'home_redirect' in the home app
    # def get_success_url(self):
    #     '''Override the default success URL to redirect to the home page after login.'''
    #     return reverse_lazy('home_redirect')  # Same as your '/' or LOGIN_SUCCESS_URL





urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('users/', include('users.urls')),
    path('leave-mgt/', include('leave_mgt.urls')),
    # path('api/', include('api.urls'), name="api"),
    
    ### allauth
    path('accounts/', include('allauth.urls')),
    ### ckeditor_5
    path("ckeditor5/", include('django_ckeditor_5.urls')),
    # path("upload/", custom_upload_function, name="custom_upload_file"), # prolly will not need this until feature for user file uploads are implemented


    ### these views/html templates are inside the "users" app
    path('login/', LoginView.as_view(template_name='auth/login.html'), name='login' ), # customized LoginView to display prompts on the page
    path('logout/', auth_views.LogoutView.as_view(template_name='auth/logout.html'), name='logout' ),
    path('register/', register, name='register' ), # for external users to sign-up only using Google accounts
    path('employee-register/', employeeRegister, name='employee-register' ), # for employees to fill-out the form, user accounts should have restrictions viewing pages on default attrs
    # path('search/', user_search_view, name="user-search"),
    
    # Password reset links (ref: https://github.com/django/django/blob/master/django/contrib/auth/views.py)
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_reset/password_change_done.html'), 
        name='password_change_done'),

    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='password_reset/password_change.html'), 
        name='password_change'),


    ### i used a subclassed pw-reset view to implement logging and for debugging puposes
    ### apparently, the {{url}} in the email is not being displayed correctly when this custom view is in use so,
    ### i returned to the default and just changed the email subject on /registration/password_reset_subject.txt
    # path('password-reset/', CustomPasswordResetView.as_view(template_name='password_reset/password_reset.html'), name='password_reset'),
    
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='password_reset/password_reset.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset-done/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset/password_reset_complete.html'),
     name='password_reset_complete'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
