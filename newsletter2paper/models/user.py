class User:
    def __init__(self, email, username, password, first_name, last_name):
        self.email = email
        self.username = username
        self.password = password  # This should be hashed
        self.first_name = first_name
        self.last_name = last_name
        self.papers = []