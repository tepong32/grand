
# 1 defining the urls as context on the view
def my_view(request):
    user_id = request.user.id  # Assuming you want to link to the logged-in user's profile
    context = {
        'navbar_items': [
            {'name': 'Home', 'icon': 'fas fa-home', 'url': reverse('home')},
            {'name': 'About', 'icon': 'fas fa-info-circle', 'url': reverse('about')},
            {'name': 'Services', 'icon': 'fas fa-cogs', 'url': reverse('services')},
            {'name': 'Profile', 'icon': 'fas fa-user', 'url': reverse('profile', kwargs={'user_id': user_id})},
        ]
    }
    return render(request, 'my_template.html', context)





