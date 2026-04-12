import requests
from tqdm import tqdm

last = 1022426
for i in tqdm(range(last - 5000, last + 1)):
    path = f"https://habr.com/ru/articles/{i}"


    url = "http://localhost:8010/ingest"

    data = {
        "url": path,
        "doc_id": f"{i}",
        "metadata": {
            "source": "habr",
            "author": "Dmitrii Garanin",
            "category": "Habr"
        }
    }

    response = requests.post(url, json=data)

    print(response.status_code)
    print(response.json())