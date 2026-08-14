from django.db import migrations


def seed_institutional_ui(apps, schema_editor):
    SiteConfiguration = apps.get_model("home", "SiteConfiguration")
    ServiceShortcut = apps.get_model("home", "ServiceShortcut")
    SiteConfiguration.objects.get_or_create(pk=1)
    shortcuts = (
        ("Request Assistance", "Submit an educational or social-assistance request through a guided process.", "fas fa-hands-helping", "/assistance/", "Start a request", 10, True),
        ("Track a Request", "Use your secure reference details to check progress without creating an account.", "fas fa-search-location", "/assistance/", "Track progress", 20, True),
        ("Public Announcements", "Read official advisories, schedules, service updates, and public notices.", "fas fa-bullhorn", "/announcements/", "View announcements", 30, False),
        ("Organization Directory", "Understand the municipal organization and find the office responsible for a service.", "fas fa-sitemap", "/orgchart/", "Explore directory", 40, False),
        ("Department Contacts", "Find verified contact details and communication channels for municipal offices.", "fas fa-address-book", "/#contact-us", "Find an office", 50, False),
        ("Employee Workspace", "Authorized employees can open their department dashboard and internal workflows.", "fas fa-user-shield", "/login/", "Employee sign in", 60, False),
    )
    for title, description, icon_class, link_url, link_label, order, featured in shortcuts:
        ServiceShortcut.objects.get_or_create(
            title=title,
            audience="public",
            defaults={
                "description": description,
                "icon_class": icon_class,
                "link_url": link_url,
                "link_label": link_label,
                "display_order": order,
                "is_featured": featured,
                "is_active": True,
            },
        )


def remove_seeded_shortcuts(apps, schema_editor):
    ServiceShortcut = apps.get_model("home", "ServiceShortcut")
    ServiceShortcut.objects.filter(
        title__in=(
            "Request Assistance",
            "Track a Request",
            "Public Announcements",
            "Organization Directory",
            "Department Contacts",
            "Employee Workspace",
        ),
        audience="public",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("home", "0003_serviceshortcut_siteconfiguration")]

    operations = [
        migrations.RunPython(seed_institutional_ui, remove_seeded_shortcuts),
    ]
