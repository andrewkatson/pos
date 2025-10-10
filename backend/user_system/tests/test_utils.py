import json

def get_response_fields(response, response_index=0):
    return get_response_content(response)

def get_response_content(response):
    return json.loads(response.content.decode("utf-8"))