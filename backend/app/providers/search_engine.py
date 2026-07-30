from app.providers.linkedin.search import LinkedInSearch
from app.providers.naukri.search import NaukriSearch


class SearchEngine:

    def __init__(self):
        self.linkedin = LinkedInSearch()
        self.naukri = NaukriSearch()

    def search(self, request):

        if request.platform.lower() == "linkedin":
            return self.linkedin.search(request)

        if request.platform.lower() == "naukri":
            return self.naukri.search(request)

        raise Exception("Unsupported platform")