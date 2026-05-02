import requests

try:
    # Send a GET request to the URL
    response = requests.get('https://papers.takara.ai/api/feed')
    
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Print the content of the response
        print(response.text)
    else:
        print(f"Failed to retrieve data. Status code: {response.status_code}")

except requests.exceptions.RequestException as e:
    print(f"An error occurred: {e}")

# read html response and extract papers from this site
# https://huggingface.co/papers/date/2026-04-30

response = requests.get('https://huggingface.co/papers/date/2026-04-30')
if response.status_code == 200:
    print(response.text)
