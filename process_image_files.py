import requests
import json
from datetime import datetime, timedelta

from azure.storage.blob import ContainerClient, ResourceTypes, AccountSasPermissions, generate_account_sas
from urllib.parse import urlparse
import traceback

# REPLACE YOUR STORAGE ACCOUNT NAME HERE
account_name = "bus5wb"
# REPLACE YOUR STORAGE ACCOUNT KEY HERE
account_key = "/+5nvgh1GNUMYON9pgjs81UTnPSCXlfy4gmzXrdYdn/ATpYCIhmpr17dK0/3P+R1iWJxRGVcalFyorRQWjg7Eg=="
# REPLACE YOUR IMAGE CONTAINER NAME HERE
container_name_images = "nycimages"
# REPLACE YOUR IMAGEMETADATA CONTAINER NAME HERE
container_name = "nycimagemetadata"

# Generate the connection string
connection_string = \
    f"DefaultEndpointsProtocol=https;" \
    f"AccountName={account_name};" \
    f"AccountKey={account_key};"


def GetSASToken():
    """Create a shared access token in order to read
        share access to the images.
       """
    sas_token = generate_account_sas(
        account_name,
        account_key=account_key,
        resource_types=ResourceTypes(object=True),
        permission=AccountSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )

    return sas_token

def GetNYCImageMetadata(image_url):
    """Use Cognitive Services to get metadata for the given image url, image url is required to have SAS appended.
       """
    # **Define function to invoke Computer Vision API**
    # Replace <MDWComputerVision Subscription Key> with your valid subscription key.
    subscription_key = "843c50d4d62a4dcf9ca4c90fe442cd45"

    # **Define function to invoke Computer Vision API**
    # Replace <MDWComputerVision Base URL> with your valid Computer Vision API base url
    vision_base_url = "https://swordofomens.cognitiveservices.azure.com/"  # It should look like this one: https://australiaeast.api.cognitive.microsoft.com/
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
    """Save the metadata for an image.
       """
    container_client = ContainerClient.from_connection_string(connection_string, container_name=container_name)

    try:
        # Instantiate a new BlobClient
        blob_client = container_client.get_blob_client(file_name)
        # Upload the blob
        blob_client.upload_blob(image_metadata, blob_type="BlockBlob")
    except Exception as e:
        print(f"Error {e}")


def CopyImages():
    """Ingest the images to the data lake.
       """

    print('Transferring images to Data Lake.')

    container = ContainerClient.from_container_url(
        container_url="https://bus5wb.blob.core.windows.net/imagecollection",
        credential="?st=2021-05-19T04%3A43%3A08Z&se=2022-05-20T04%3A43%3A00Z&sp=rl&sv=2018-03-28&sr=c&sig=yV19KD0EzGYQOecRpa2em6Fc6IRQ7%2FhowiAaO%2Bk70O4%3D"
    )
    container_client = ContainerClient.from_connection_string(connection_string, container_name=container_name_images)

    blobs_list = container.list_blobs()

    for blob in blobs_list:
        blob_client = container.get_blob_client(blob.name)
        nycImageUrl = blob_client.url

        # Generate filename for image metadata file.
        filePath = urlparse(nycImageUrl)[2]
        filePathParts = filePath.split('/')
        fileName = filePathParts[len(filePathParts) - 1]

        try:
            # Instantiate a new BlobClient
            blob_client = container_client.get_blob_client(fileName)
            # Upload the blob
            blob_client.start_copy_from_url(nycImageUrl)
        except Exception as e:
            print(f"Error {e} - {fileName} - {nycImageUrl}")

def GetFilePathFromImageURL(url):
    filePath = urlparse(url)[2]
    filePathParts = filePath.split('/')
    fileName = filePathParts[len(filePathParts) - 1] + '.json'
    return fileName

def ProcessAllImages():

    print('Processing Images.')

    container = ContainerClient.from_connection_string(connection_string, container_name=container_name_images)

    blobs_list = container.list_blobs()

    token = GetSASToken()

    for blob in blobs_list:
        blob_client = container.get_blob_client(blob.name)

        # Generate filename for image metadata file.
        fileName = GetFilePathFromImageURL(blob_client.url)
        nycImageUrl = f'{blob_client.url}?{token}'

        try:
            jsonImageMetadata = GetNYCImageMetadata(nycImageUrl)
            SaveImageMetadata(jsonImageMetadata, fileName)

            print(f'Completed processing {fileName}.')
        except Exception as e:
            print(f"Error {e} - {fileName}")
            # print(traceback.format_exc())

print('Commence processing.')
# Execution Sequence
# Copy images from the source to the datalake
CopyImages()
# Loop through the images in the datalake and process them
ProcessAllImages()
print('Processing complete.')
