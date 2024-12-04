templating-related folder:

Django uses the following templates for password reset emails:

    registration/password_reset_email.html: This is the default email template sent to users when they request a password reset. NO NEED TO CHANGE THIS AS CUSTOMIZING VIEWS FAILS TO DISPLAY THE RESET_URL TO THE EMAIL THAT'S BEING SENT.

    registration/password_reset_subject.txt: If you want to customize the email subject/title, use this.
