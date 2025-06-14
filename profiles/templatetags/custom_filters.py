from django import template

register = template.Library()

@register.filter(name='length_is')
def length_is(value, length):
    return len(value) == length


# or pip install django-length 

@register.filter
def currency(value):
    return "P{:,.2f}".format(value)


### these two are not being used atm
@register.filter
def get_item(dictionary, key):
    """
    Returns the value for a given key from a dictionary.   
    :param dictionary: The dictionary to search.
    :param key: The key to look for in the dictionary.
    :return: The value associated with the key, or None if the key is not found.
    """
    return dictionary.get(key)

@register.filter
def employment_color(emp_type):
    '''
    Returns a color class based on the employment type.
    NOT YET implemented.'''
    """
    Returns a color class based on the employment type.
    :param emp_type: Employment type (e.g., 'REG', 'JO', 'COS', 'COTERMINOUS')
    :return: Corresponding color class as a string.
    """
    colors = {
        'REG': 'primary',
        'JO': 'warning',
        'COS': 'info',
        'COTERMINOUS': 'secondary',
    }
    return colors.get(emp_type.upper(), 'dark')
