from datetime import datetime

def get_filename(filename, request):
    '''
    File naming control for CKEditor uploads
    '''
    # Get the username from the request
    username = request.user.username if request.user.is_authenticated else 'anonymous'
    
    # Get the current date in the desired format
    date_str = datetime.now().strftime('%Y%m%d')  # Format: YYYYMMDD
    
    # Generate the new filename
    new_filename = f"{username}-{date_str}-{filename}"
    
    return new_filename