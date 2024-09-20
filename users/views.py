from django.shortcuts import render, redirect
from .models import User
from django.contrib import messages     # for flash messages regarding valid data in the form


# for needing user to be logged-in first before accessing the page requested
from django.contrib.auth.decorators import login_required
from .forms import *

def usersIndexView(request):
    user = User
    context_data = {
        # all users sorted by latest "date_joined" attr, paginating by 50 per page
        'users': user.objects.all().order_by("-date_joined")[:50],
        'userCount': user.objects.count(),
    }

    return render(request, 'users/users_index.html', context_data)


def register(request):
    '''
        if the page gets a POST request, the POST's data gets instantiated to the UserCreationForm,
        otherwise, it instantiates a blank form.
    '''
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()     # to make sure that the registering user gets saved to the database
            username = form.cleaned_data.get("username")
            messages.success(request, f"Account created for {username}! You can now log in.")
            return redirect("login")
    else:
        form = UserRegisterForm()
    # arguments == "request", the_template, the_context(dictionary))
    return render(request, 'auth/register.html', {'form': form})


@login_required
def profileView(request, username=None):
    if User.objects.get(username=username):
        user = User.objects.get(username=username)
        return render(request, 'users/profile.html',
            {
                "user": user,
            }
        )
    else:
        return render ("User not found.")



@login_required
def profileEditView(request, username=None):
    if User.objects.get(username=username):
        user = User.objects.get(username=username)
        if request.method == 'POST':    # for the new info to be saved, this if block is needed
            # the forms from forms.py
            u_form = UserUpdateForm(request.POST, request.FILES, instance=request.user)        # instance is for the fields to auto-populate with user info
            p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)

            if u_form.is_valid():
                u_form.save()
                p_form.save()
                messages.success(request, f"Account info has been updated.")
                return render(request, "users/profile.html", {"user":user})

        else:
            u_form = UserUpdateForm(instance=request.user)
            p_form = ProfileUpdateForm(instance=request.user)

        context = {
            'u_form': u_form,
            'p_form': p_form
        }
        return render(request, 'users/profile_edit.html', context)

    else:
        return render ("User not found.")


### accounts/users searching view
### not used ATM
def user_search_view(request, *args, **kwargs):
    context = {}
    if request.method == "GET":
        search_query = request.GET.get("q")
        if len(search_query) > 0:
            search_results = User.objects.filter(username__icontains=search_query).filter(email__icontains=search_query).distinct()
            user = request.user
            accounts = [] # [(account1, True), (account2, False), ...]
            for account in search_results:
                accounts.append((account, False)) # you have no friends yet
            context['accounts'] = accounts
                
    return render(request, "users/user_search_results.html", context)

