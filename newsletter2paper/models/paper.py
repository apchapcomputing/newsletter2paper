class Paper:
    def __init__(self, publications, format, email, frequency):
        self.publications = publications  # List of Publication objects
        self.format = format  # 'newspaper' or 'essay'
        self.email = email
        self.frequency = frequency  # How often to generate and send