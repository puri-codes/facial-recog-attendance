from django.shortcuts import redirect, render
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import LoginForm


def login_view(request):
    """Handle user login with role-based redirect."""
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            request.session.pop('bypass_login_paused', None)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            if next_url:
                return redirect(next_url)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'next_url': next_url,
    })


def logout_view(request):
    """Log out the user."""
    if request.user.is_authenticated:
        logout(request)
        request.session['bypass_login_paused'] = True
        messages.info(request, 'You have been logged out.')
    return redirect('accounts:login')


def home_redirect(request):
    """Redirect users based on authentication status and role."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    if request.user.role == 'admin':
        return redirect('academics:admin_dashboard')
    elif request.user.role == 'teacher':
        return redirect('attendance:teacher_dashboard')
    elif request.user.role == 'student':
        return redirect('attendance:student_dashboard')
    return redirect('accounts:login')
