import requests
import json

from azure.storage.blob import ContainerClient
from urllib.parse import urlparse

# REPLACE YOUR STORAGE ACCOUNT NAME HERE
account_name = "<synapsedatalake account name>"
# REPLACE YOUR STORAGE ACCOUNT KEY HERE
account_key = "<synapsedatalake key>"
# REPLACE YOUR CONTAINER NAME HERE
container_name = "nycimagemetadata"

# Generate the connection string
connection_string = \
    f"DefaultEndpointsProtocol=https;" \
    f"AccountName={account_name};" \
    f"AccountKey={account_key};"


def GetNYCImageMetadata(image_url):

    # **Define function to invoke Computer Vision API**
    # Replace <MDWComputerVision Subscription Key> with your valid subscription key.
    subscription_key = "<ADPComputerVision Subscription Key>"

    # **Define function to invoke Computer Vision API**
    # Replace <MDWComputerVision Base URL> with your valid Computer Vision API base url
    vision_base_url = "<ADPComputerVision Base URL>"  # It should look like this one: https://australiaeast.api.cognitive.microsoft.com/
    analyze_url = vision_base_url + "vision/v2.0/analyze"

    # Populate require request information
    headers = {'Ocp-Apim-Subscription-Key': subscription_key}
    params = {'visualFeatures': 'Categories,Description,Color,Brands,Tags,Objects', 'details': 'Landmarks,Celebrities'}
    data = {'url': image_url}

    # Submit Computer Vision request for given image url
    response = requests.post(analyze_url, headers=headers, params=params, json=data)
    response.raise_for_status()

    # The 'analysis' object contains various fields that describe the image. The most
    # relevant caption for the image is obtained from the 'description' property.
    analysis = response.json()
    return json.dumps(analysis).replace('"requestId"', '"imageUrl":"' + image_url + '","requestId"')


# New blob write method using ADF Custom Activity
def SaveImageMetadata(image_metadata, file_name):
    container_client = ContainerClient.from_connection_string(connection_string, container_name=container_name)

    try:
        # Instantiate a new BlobClient
        blob_client = container_client.get_blob_client(file_name)
        # Upload the blob
        blob_client.upload_blob(image_metadata, blob_type="BlockBlob")
    except Exception as e:
        print(f"Error {e}")


def ProcessAllImages():
    container = ContainerClient.from_container_url(
        container_url="https://bus5wb.blob.core.windows.net/imagecollection",
        credential="?st=2020-06-02T12%3A45%3A46Z&se=2020-07-02T12%3A45%3A00Z&sp=rl&sv=2018-03-28&sr=c&sig=EaT4rrzQoO%2FOe8yDWkibedUb2p58ixeOfHpqBEsu2FQ%3D"
    )

    blobs_list = container.list_blobs()

    for blob in blobs_list:
        blob_client = container.get_blob_client(blob.name)
        nycImageUrl = blob_client.url

        # Generate filename for image metadata file.
        filePath = urlparse(nycImageUrl)[2]
        filePathParts = filePath.split('/')
        fileName = filePathParts[len(filePathParts) - 1] + '.json'

        try:
            jsonImageMetadata = GetNYCImageMetadata(nycImageUrl)
            SaveImageMetadata(jsonImageMetadata, fileName)
        except Exception as e:
            print(f"Error {e} - {fileName}")


ProcessAllImages()
