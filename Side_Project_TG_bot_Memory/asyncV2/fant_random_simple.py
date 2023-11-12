import requests
from bs4 import BeautifulSoup
import re
import random
from retrying_async import retry


@retry(attempts=3)
async def random_parsed():

    urls = ['https://www.fantlab.ru/compare',
            'https://fantlab.ru/ratings',
            'https://fantlab.ru/news',
            'https://fantlab.ru/bygenre',
            'https://fantlab.ru/pubnews',
            'https://fantlab.ru']

    url = random.choice(urls)

    work_number = None

    # Define headers for the request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/58.0.3029.110 Safari/537.3',
    }

    # Define parameters to disable images
    params = {
        'images': 0,
    }
    try:
        # Make a GET request to the website with headers and parameters
        response = requests.get(url, headers=headers, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the specific section containing the random work information
            work_info_div = soup.find('div', {'id': 'wg-randomwork'})

            # Check if the work_info_div is found
            if work_info_div:
                # Extract the work number from the href attribute
                link_tag = work_info_div.find('b').find('a')
                if link_tag:
                    href_value = link_tag.get('href')
                    work_number_match = re.search(r'/work(\d+)', href_value)

                    if work_number_match:
                        work_number = work_number_match.group(1)
                        print(f"The work number is: {work_number}")
                        return work_number

                    else:
                        raise ValueError("Work number not found on the page")
                else:
                    raise ValueError("Link tag not found in the 'wg-randomwork' section.")
            else:
                raise ValueError("Specific section 'wg-randomwork' not found on the page.")
        else:
            raise requests.RequestException(f"Error: {response.status_code}")

    except Exception as e:
        print('Simple parse for fantlab random work failed')
        return None
