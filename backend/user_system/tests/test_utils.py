import json

def get_response_fields(response, response_index=0):
    content_as_json = get_response_content(response)
    if len(content_as_json) == 1:
        return content_as_json[response_index]['fields']
    else:
        raise AssertionError(f"Response had zero or more than one responses when only one was desired {content_as_json}")

def get_response_content(response):
    return json.loads(json.loads(response.content.decode("utf-8"))['response_list'])