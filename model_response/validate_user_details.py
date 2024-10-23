import os
import re
import time


class ValidateUserDetails:
    @staticmethod
    def check_valid_input(user_input):
        """Checks if the user input is a valid input."""
        return (
            isinstance(user_input, str)
            and len(user_input) <= 1500
            and user_input.strip() != ""
        )

    @staticmethod
    def check_name(name):
        """Check if the name is valid."""
        # Use regular expression to validate name format
        print(f"Name check: ", name)
        pattern = r"^[a-zA-Z ]+$"
        if re.match(pattern, name):
            return True
        else:
            return False

    @staticmethod
    def check_email(email):
        """Check if the email is valid."""
        # Use regular expression to validate email format
        print(f"Email check: ", email)
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if re.match(pattern, email):
            return True
        else:
            return False

    @staticmethod
    def check_phone(phone):
        """Check if the phone number is valid."""
        # Use regular expression to validate phone number format
        print(f"Phone check: ", phone)
        pattern = r"^\+?[0-9 ]+$"
        if re.match(pattern, phone):
            return True
        else:
            return False

    @staticmethod
    def check_age(age):
        """Check if the age is valid."""
        if not age or age == "None":
            return False
        # Check if the age is a number
        if 0 < int(age) < 120:
            print(f"Age check: Passed")
            return True
        else:
            print(f"Age check: Failed")
            return False

    @staticmethod
    def check_country_code(country_code):
        """Check if the country code is valid."""
        # Use regular expression to validate country code format
        print(f"Country code check: ", country_code)
        pattern = r"^\+?[0-9]+$"
        if re.match(pattern, country_code):
            return True
        else:
            return False
