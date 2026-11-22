def is_even(number):
    """Return True if number is even."""
    return number % 2 == 0


for value in [1, 2, 3, 4]:
    print(value, is_even(value))
