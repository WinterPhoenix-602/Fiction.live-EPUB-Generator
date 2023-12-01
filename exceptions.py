class StoryDoesNotExist(Exception):
    def __init__(self,url):
        self.url=url

    def __str__(self):
        return f"Story does not exist: ({self.url})"
    
class AdultCheckRequired(Exception):
    def __init__(self,url):
        self.url=url

    def __str__(self):
        return f"Story requires confirmation of adult status: ({self.url})"