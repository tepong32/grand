from django.contrib import admin
from django.contrib.auth import views as auth_views     # for auths for logins and logouts
from django.urls import path, include
from users.views import (
    register,
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





urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls'), name="home"),
    path('users/', include('users.urls'), name="users"),
    path('leave-mgt/', include('leave_mgt.urls'), name="leave_mgt"),
    # path('api/', include('api.urls'), name="api"),
    
    ### allauth
    path('accounts/', include('allauth.urls')),


    ### these views/html templates are inside the "users" app
    path('login/', LoginView.as_view(template_name='auth/login.html'), name='login' ), # customized LoginView to display prompts on the page
    path('logout/', auth_views.LogoutView.as_view(template_name='auth/logout.html'), name='logout' ),
    path('register/', register, name='register' ),
    # path('search/', user_search_view, name="user-search"),
    
    # Password reset links (ref: https://github.com/django/django/blob/master/django/contrib/auth/views.py)
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_reset/password_change_done.html'), 
        name='password_change_done'),

    path('password-change/', auth_views.PasswordChangeView.as_view(template_name='password_reset/password_change.html'), 
        name='password_change'),

    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='password_reset/password_reset_confirm.html'),
        name='password_reset_confirm'),
    ### i used a subclassed pw-reset view to implement logging and for debugging puposes
    path('password-reset/', CustomPasswordResetView.as_view(template_name='password_reset/password_reset.html'), name='password_reset'),
    
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='password_reset/password_reset_complete.html'),
     name='password_reset_complete'),

]


from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)