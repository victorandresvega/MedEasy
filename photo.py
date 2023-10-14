import base64

import requests

class Photo:
    @staticmethod
    def encodeImage(path_or_url):
        if path_or_url.startswith("static/"):
            with open(path_or_url, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        response = requests.get(path_or_url)
        return base64.b64encode(response.content).decode('utf-8')

        
    @staticmethod
    def decodeImage(encoded_string):
        """
        Decode the Base64 encoded string to a data URI for use in HTML img src.

        Parameters:
        - encoded_string: Base64 encoded string.

        Returns:
        - Data URI string.
        """
        return f"data:image/jpeg;base64,{encoded_string}"
