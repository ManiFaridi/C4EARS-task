import requests
import time
import random

BASE_URL = 'https://url'
TOKEN = 'the.jwt_token.for_the_ml_server'

HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

def fetch_request():
    response = requests.get(f'{BASE_URL}/fetch-requests', headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f'Error fetching request: {response.json()}')
        return None

def submit_result(request_id, result):
    data = {'request_id': request_id, 'result': result}
    response = requests.post(f'{BASE_URL}/submit-result', json=data, headers=HEADERS)
    if response.status_code == 200:
        print(f'Result submitted for request ID: {request_id}')
    else:
        print(f'Error submitting result: {response.json()}')

def main():
    while True:
        request_data = fetch_request()
        if request_data:
            request_id = request_data['request_id']
            query = request_data['query']
            # Simulate processing time
            time.sleep(random.uniform(1, 5))
            result = f"Processed query: {query}"
            submit_result(request_id, result)
        else:
            print('No requests to process. Waiting...')
            time.sleep(10)

if __name__ == '__main__':
    main()
