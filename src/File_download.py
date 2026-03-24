import requests
import shutil
import os
from datetime import datetime,date,timedelta

USERNAME = "Copernicus_login"
PASSWORD = "Copernicus_password"
OUTPUT_FILENAME = "../Data/sentinel_image.zip"





def get_auth_token(user, password):
    print("1/3 Loging to system...")
    token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

    data = {
        "client_id": "cdse-public",
        "username": user,
        "password": password,
        "grant_type": "password",
    }

    response = requests.post(token_url, data=data)

    if response.status_code == 200:
        print(f"Status:{response.status_code}-Login successful")

        return response.json()["access_token"]
    else:
        print(f"Login Error-Status:{response.text}")
        return None


def find_and_download_image(token):
    headers = {"Authorization": f"Bearer {token}"}


    print("2/3 Searching for an image in the OData directory...")


    today_date = date.today().strftime("%Y-%m-%d")
    earlier_date = datetime.fromisoformat(today_date) + timedelta(days=-10)
    earlier_date=earlier_date.strftime("%Y-%m-%d")
    start_date="2024-08-18"
    end_date="2024-08-20"
    cloud_coverage="25.00"
    filter_query = (
        "Collection/Name eq 'SENTINEL-2' and "
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/Value eq 'S2MSI2A') and "
        f"ContentDate/Start ge {start_date}T00:00:00Z and "
        f"ContentDate/Start le {end_date}T00:00:00Z and "
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/Value le {cloud_coverage}) and "
        "OData.CSC.Intersects(area=geography'SRID=4326;POLYGON((-93.6 42.0, -93.5 42.0, -93.5 42.1, -93.6 42.1, -93.6 42.0))')"
    )

    search_url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$filter={filter_query}&$top=1&$orderby=ContentDate/Start desc&$expand=Attributes"

    search_response=requests.get(search_url, headers=headers)
    search_data=search_response.json()
    print(search_data)
    if not search_data.get('value'):
        print("No photos found for these criteria")
        return


    best_product=search_data['value'][0]
    product_id=best_product['Id']
    product_name=best_product['Name']
    cloud_cover =""
    date_of_picture=best_product['ContentDate']
    print(best_product['Attributes'])
    for attr in best_product['Attributes']:
        if attr['Name']=='cloudCover':
            cloud_cover=attr['Value']

    print(f"ID: {product_id}")
    print(f"Name:{product_name}")
    print(f"Cloud_cover:{cloud_cover}%")
    print(f"Execution date:{date_of_picture}%")


    print(f"3/3 starting to download the file {OUTPUT_FILENAME}...")
    download_url=f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value"

    with requests.get(download_url,headers=headers,stream=True) as r:
        r.raise_for_status()
        with open(OUTPUT_FILENAME, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    print(f"SUCCESS File saved as: {os.path.abspath(OUTPUT_FILENAME)}")


if __name__ == "__main__":
    my_token = get_auth_token(USERNAME, PASSWORD)

    if my_token:
        find_and_download_image(my_token)